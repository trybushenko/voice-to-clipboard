import sys
from collections import deque
import numpy as np

SAMPLE_RATE = 16000
BLOCK = 1024                 # ~64 мс
WEBRTC_FRAME = 480           # 30 мс — webrtcvad приймає тільки 10/20/30 мс
VAD_WINDOW = 16              # кадрів (~480 мс) для мажоритарного рішення
VAD_RATIO = 0.35             # частка кадрів-мовлення у вікні
VAD_MIN_OVER_FLOOR = 3.0     # VAD сам-один не тримає лінію біля рівня шуму
FLOOR_WINDOW = 5             # блоків (~320 мс) для оцінки шумового фону
PEAK_HEADROOM_DB = 6.0       # поріг мінімум на стільки нижче робочого рівня
ABS_MIN_DB = -58.0           # нижче цього не опускаємось (шум АЦП)
PEAK_DECAY_DB = 0.15         # спад піку за блок (~2.3 dB/с)
STUCK_WARN_S = 45.0          # попередити, якщо "мовлення" не вщухає

def dbfs(x):
    return 20.0 * np.log10(float(np.sqrt(np.mean(x ** 2))) + 1e-9)


class SpeechGate:
    """Стан "мовлення / тиша" і довжина поточної паузи.

    Два детектори по АБО, але WebRTC VAD не має права сам-один тримати лінію,
    якщо рівень сигналу біля шумового фону — інакше кулер і клавіатура не
    дають лічильнику паузи набратись і автостоп не спрацьовує ніколи.
    """

    def __init__(self, mode="auto", margin_min=6.0, margin_max=12.0,
                 hysteresis=4.0, aggressiveness=2):
        self.vad = None
        if mode in ("auto", "webrtc"):
            try:
                import webrtcvad
                self.vad = webrtcvad.Vad(aggressiveness)
            except ImportError:
                if mode == "webrtc":
                    sys.exit("webrtcvad is not installed: "
                             "pip install webrtcvad-wheels")
        self.margin_min = margin_min
        self.margin_max = margin_max
        self.hysteresis = hysteresis

        self._tail = np.zeros(0, dtype=np.float32)
        self._vad_frames = deque(maxlen=VAD_WINDOW)
        self._recent = deque(maxlen=FLOOR_WINDOW)
        self._floor_db = None
        self._peak_db = -120.0

        self.in_speech = False
        self.speech_total = 0.0
        self.silence_run = 0.0
        self.speech_run = 0.0
        self.last_db = -120.0
        self.vad_hit = False

    @property
    def floor_db(self):
        # Без стелі: вона недооцінювала фон у шумних кімнатах, поріг падав під
        # рівень шуму і запис не зупинявся. Замість неї — прив'язка до піку.
        return self._floor_db if self._floor_db is not None else ABS_MIN_DB

    @property
    def threshold_db(self):
        floor = self.floor_db
        span = self._peak_db - floor
        margin = float(np.clip(0.4 * span, self.margin_min, self.margin_max))
        enter = floor + margin
        # Поріг зобов'язаний бути нижче робочого рівня голосу, інакше тихе
        # мовлення без паузи (фон калібрується на сам голос) обривається.
        if self._peak_db > ABS_MIN_DB:
            enter = min(enter, self._peak_db - PEAK_HEADROOM_DB)
        enter = max(enter, ABS_MIN_DB)
        return enter - self.hysteresis if self.in_speech else enter

    def _update_levels(self, block):
        self._recent.append(float(np.mean(block ** 2)))
        if len(self._recent) == FLOOR_WINDOW:
            window_db = 10.0 * np.log10(float(np.mean(self._recent)) + 1e-18)
            self._floor_db = (window_db if self._floor_db is None
                              else min(self._floor_db, window_db))
        self._peak_db = max(self.last_db, self._peak_db - PEAK_DECAY_DB)

    def _webrtc_speech(self, block):
        """Мажоритарне рішення по вікну ~480 мс: сирий webrtcvad дає близько
        10% ложних спрацювань, і одиничний хибний кадр скидав би паузу."""
        if self.vad is None:
            return False
        buf = np.concatenate([self._tail, block])
        n = len(buf) // WEBRTC_FRAME
        for i in range(n):
            frame = buf[i * WEBRTC_FRAME:(i + 1) * WEBRTC_FRAME]
            pcm = np.clip(frame * 32767.0, -32768, 32767).astype(np.int16)
            try:
                self._vad_frames.append(
                    1 if self.vad.is_speech(pcm.tobytes(), SAMPLE_RATE) else 0
                )
            except Exception:
                self.vad = None
                return False
        self._tail = buf[n * WEBRTC_FRAME:]
        if not self._vad_frames:
            return False
        return (sum(self._vad_frames) / len(self._vad_frames)) >= VAD_RATIO

    def push(self, block):
        dur = len(block) / SAMPLE_RATE
        self.last_db = dbfs(block)
        self._update_levels(block)

        energy = self.last_db > self.threshold_db
        self.vad_hit = self._webrtc_speech(block)
        # VAD враховується лише якщо сигнал помітно вище фону.
        vad_ok = self.vad_hit and self.last_db > self.floor_db + VAD_MIN_OVER_FLOOR
        speech = energy or vad_ok

        if speech:
            self.in_speech = True
            self.speech_total += dur
            self.speech_run += dur
            self.silence_run = 0.0
        else:
            self.in_speech = False
            self.speech_run = 0.0
            if self.speech_total > 0:
                self.silence_run += dur

    @property
    def armed(self):
        """Чи можна обривати — тобто чи щось уже реально було сказано."""
        return self.speech_total >= 0.35


"""Перевірка SpeechGate на синтетичному сигналі без мікрофона."""
import numpy as np
import dictate as d

SR, B = d.SAMPLE_RATE, d.BLOCK
rng = np.random.default_rng(0)

def noise(sec, db=-60):
    amp = 10 ** (db / 20)
    return rng.normal(0, amp, int(sec * SR)).astype(np.float32)

def speech(sec, db=-28):
    """Груба імітація: модульований тон + шум, рівень db."""
    t = np.arange(int(sec * SR)) / SR
    sig = (np.sin(2*np.pi*180*t) * (0.6 + 0.4*np.sin(2*np.pi*3.5*t))
           + 0.3*np.sin(2*np.pi*420*t))
    sig = sig / np.abs(sig).max()
    amp = 10 ** (db / 20)
    return (sig * amp + noise(sec, -60)).astype(np.float32)

def run(signal, label, silence=4.0):
    gate = d.SpeechGate(mode="auto")
    n = len(signal) // B
    fired_at = None
    for i in range(n):
        gate.push(signal[i*B:(i+1)*B])
        t = (i+1)*B/SR
        if fired_at is None and gate.armed and gate.silence_run >= silence:
            fired_at = t
    print(f"{label:44s} floor={gate.floor_db:6.1f} "
          f"speech={gate.speech_total:5.1f}s  "
          f"cut={'ні' if fired_at is None else f'{fired_at:.1f}s'}")
    return fired_at

def main():
    print("WebRTC VAD доступний:", d.SpeechGate(mode="auto").vad is not None)
    print()

    # 1. Головний баг попередньої версії: говорити з нульової секунди.
    run(np.concatenate([speech(12, -28), noise(1.0)]),
        "мовлення з 0-ї с, пауза 1с всередині -> не рубати")

    # 2. Довга пауза на роздуми посеред диктування.
    run(np.concatenate([speech(4, -28), noise(2.5), speech(5, -28), noise(1.0)]),
        "пауза 2.5с на роздуми -> не рубати")

    # 3. Реальний кінець: 5 секунд тишi.
    run(np.concatenate([speech(4, -28), noise(6.0)]),
        "кінець: тиша 6с -> рубати ~на 8с")

    # 4. Тихе мовлення (не підвищуючи тон).
    run(np.concatenate([speech(6, -42), noise(1.0)]),
        "тихе мовлення -42dBFS -> не рубати")

    # 5. Пауза на початку, потім мовлення.
    run(np.concatenate([noise(5.0), speech(5, -28), noise(1.0)]),
        "тиша 5с на початку -> не рубати (не armed)")

    # 6. Шумна кімната.
    run(np.concatenate([speech(6, -25) + noise(6, -45), noise(1.0, -45)]),
        "шумна кімната (фон -45) -> не рубати")

    print()
    # 7. Довга пауза на роздуми — 3.5с, має вижити при --silence 4
    run(np.concatenate([speech(3, -28), noise(3.5), speech(4, -28), noise(1.0)]),
        "пауза 3.5с -> не рубати (silence=4)")
    # 8. Реалістично тихий диктор
    run(np.concatenate([speech(5, -38), noise(0.4), speech(4, -38), noise(6.0)]),
        "тихий диктор -38dBFS, пауза 0.4с -> рубати в кінці")
    # 9. Довге диктування з багатьма паузами
    seg = [speech(3, -30), noise(1.5), speech(2, -30), noise(2.0),
           speech(4, -30), noise(0.8), speech(3, -30), noise(6.0)]
    run(np.concatenate(seg), "20с з 4 паузами -> рубати тільки в кінці")


if __name__ == "__main__":
    main()

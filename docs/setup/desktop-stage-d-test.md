# Тестування етапу D: desktop, tray та автозапуск

Гілка `codex/desktop-tray-autostart`; main містить прийняті B/C.
Це developer installation. Готовий installer без Python/Git — наступний етап E.
Після pull завжди перевстановлюй пакет. Історія й моделі залишаються на місці.

## Windows: встановлення й перший запуск

Заверши диктування, закрий старий host і в папці репозиторію виконай:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
.\.venv\Scripts\dictate.exe --unload-model
git fetch --prune origin
git switch --track origin/codex/desktop-tray-autostart
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys,desktop]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/check_desktop.py
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app --install
```

Якщо гілка вже є: `git switch codex/desktop-tray-autostart`, `git pull --ff-only`,
потім pip install. Якщо venv названо `venv`, заміни `.venv` у всіх командах.
Якщо старий host не запущений, повідомлення `host unavailable` від Quit нормальне.
Автотести не записують голос; desktop smoke має надрукувати PASS і прибрати свій UI.

Після install знайди **Voice to Clipboard** у Start Menu й запусти звідти.
**PowerShell більше не потрібен для щоденної роботи.** Вікна консолі не має бути.
Іконка мікрофона може спочатку бути в прихованих іконках трею — розгорни їх.
Альтернативний перший запуск: `.\.venv\Scripts\voice-desktop.exe`.

## Основний сценарій

1. Закрий усі термінали. У Блокноті, браузері та VS Code перевір U/E/L як у B/C.
2. Колір/статус іконки: idle → starting/recording → transcribing → delivered → idle.
   Error і disabled показуються окремо. Оверлей не забирає фокус.
3. Меню іконки → Start Ukrainian або Start English: голос записується, Stop recording
   завершує його, текст потрапляє в clipboard. Start із меню — copy-only; для
   автовставки в початкове поле використовуй L з редактора.
4. Мікрофон не активний у idle. Нові стартові натискання не створюють паралельні записи.
5. Copy last transcript повертає останній текст у clipboard без нового запису.
6. Запусти Voice to Clipboard зі Start Menu ще раз: відкриється панель статусу,
   не друга іконка/host. Повтори кілька разів — одна панель і той самий PID.

За потреби перевір PID та фазу:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --status
```

У відповіді `desktop: true`, `pid`, `phase`, `dictation_processes`, `worker_pid`.
Desktop worker має власний runtime; `dictate --model-status` показує legacy CLI worker,
а не desktop worker. Для desktop перевіряй PID через host status/Task Manager.

## Пауза, settings і конфлікти

- Pause shortcuts вимикає тільки shortcuts. Активний запис продовжується;
  заверши його Stop recording з меню/панелі. Resume повертає shortcuts.
- Settings / System check: зміни modifiers на `ctrl+alt`, Apply. Перевір U/E/L
  з новими modifiers, потім перезапусти app — налаштування мають зберегтися.
- Поверни `alt+shift`, якщо не конфліктує з перемиканням розкладки Windows.
- Спробуй невалідні modifiers: зрозуміла помилка, попередні shortcuts працюють.
- Якщо інша програма зайняла нову комбінацію, Apply має відмовити та відновити
  попередню конфігурацію. Не має залишитися половини зареєстрованих shortcuts.
- Під час запису зміна settings відхиляється з поясненням завершити сесію.
- Overlay on/off змінює наступну сесію. Model empty використовує попередні defaults.
  Inference device CPU/CUDA/Metal/auto не встановлює драйверів і не завантажує
  модель до початку запису. На Windows не обирай Metal.
- Check system показує runtime, backend, audio inputs, writable data і permission hints.
  Він не вмикає мікрофон. Для CUDA реальне мовлення — окрема перевірка, не зелений doctor.

## Автозапуск — обов'язкова перевірка

1. Меню/Settings → Start at login: увімкни.
2. Вийди з app через Quit і відкрий знову: прапорець увімкнений, другий startup entry
   не створився. Повторне ввімкнення idempotent.
3. **Sign out → sign in** у Windows, не відкривай PowerShell.
4. Іконка з'являється сама; U/E/L працюють з редактора.
5. Закрий термінали, якщо вони були відкриті: app працює далі.
6. Вимкни Start at login. Знову sign out/sign in: app не стартує.
7. Ручний Start Menu запуск після цього працює.

Використовується тільки власна value `com.trybushenko.voicetoclipboard` у
HKCU\Software\Microsoft\Windows\CurrentVersion\Run. Адміністратор не потрібен.
Windows може окремо вимкнути startup app у Task Manager/Settings — перевір це,
якщо прапорець app увімкнений, а запуск при вході заблокований ОС.

## Quit, cancel і процеси

1. Quit у idle: іконка/панель зникають, shortcuts звільнені, worker PID завершується.
2. Запиши коротку U-фразу; Quit під час запису: stop → tail → clipboard → exit.
3. Повтори Quit під час transcribing і cold model load. Іконка показує shutting-down;
   звичайний Quit чекає до 120 секунд, потім завершує свої процеси.
4. Під час очікування доступне **Cancel unfinished dictation and exit**.
   Це явне скасування: незавершений текст може бути втрачений.
5. Після нормального Quit/Cancel не повинні лишатися процеси цього desktop-host,
   його recorder, worker, overlay чи settings panel. Інші Python-програми не чіпаються.
6. Повторний запуск після кожного сценарію працює. Виконай 10 циклів start/quit.
7. Окремий CLI recorder не повинен отримувати stop від desktop, якщо desktop не
   володіє цим записом. Глобальний session lock не дозволяє двом recorder одночасно
   зайняти мікрофон; другий має пояснити, що попередня сесія ще активна.

## Журнал і помилки

Меню Open log відкриває `%LOCALAPPDATA%\VoiceToClipboard\logs\desktop.log`.
Поточний файл до 512 KiB, максимум три backups. Там стани, коди/типи технічних
подій, помилки controller; **немає transcript/audio**. Історія диктування зберігається
окремо за старими правилами. Не надсилай приватну history.json у bug report.

Перевір відсутній/заборонений мікрофон, неправильну модель та недоступний CUDA:
error у стані/панелі, app не падає, наступна сесія після виправлення налаштувань працює.
Довільний stderr ML-бібліотек не записується як текст у журнал; для повного traceback
можна повторити збій через звичайний CLI у foreground.

## macOS, особливо M4

Використовуй **arm64 Python**, без Rosetta:

```bash
python3 -c 'import platform; print(platform.machine())'
python3 -m pip install '.[mac,hotkeys,desktop]'
python3 -m voice_to_clipboard.ui.desktop_app --install
open "$HOME/Applications/Voice to Clipboard.app"
```

Команди запускаються Python того venv, де встановлений проєкт. Після install
запуск із Finder → Applications/Voice to Clipboard.app; menu bar icon.
Дозволь Microphone, Accessibility та Input Monitoring для застосунку/використаного
Python у System Settings. При відсутньому Accessibility host має залишатися
доступним із disabled shortcuts; Resume після надання дозволу.

Перевір ті самі recording/settings/quit сценарії. Start at login створює один
`~/Library/LaunchAgents/com.trybushenko.voicetoclipboard.plist`; після наступного
login запускається app. KeepAlive вимкнено: Quit не спричиняє автоматичний restart.
Вимкнення startup видаляє цей файл і діє для наступного login.

Це **unsigned developer .app bootstrap**, прив'язаний до встановленого venv,
зі stable bundle ID. Перенесення/видалення venv потребує повторного install.
Включений runtime, Developer ID signing і notarization належать packaging E;
не вимикай Gatekeeper глобально. Фізичний M4/permission/login test — ручний gate.

## Linux

```bash
venv/bin/python -m pip install '.[whisper,hotkeys,desktop]'
venv/bin/python -m voice_to_clipboard.ui.desktop_app --install
venv/bin/voice-desktop
```

Потрібні system GI/GTK bindings для Python: на Debian/Ubuntu `python3-gi`,
`gir1.2-gtk-3.0`; для сучасного GNOME tray — AppIndicator/Ayatana bindings
(`gir1.2-ayatanaappindicator3-0.1` або відповідний пакет дистрибутива) та підтримка
індикаторів у DE. Використовуй відповідний system Python venv; `.so` GI від іншої
версії Python несумісний. App не встановлює системні пакети потайки.

Без AppIndicator використовується GTK fallback. Якщо DE не показує GTK tray,
відкривається control panel; повторний запуск launcher теж відкриває панель.
Для постійної видимої іконки встанови підтримку tray у DE.

Launcher: XDG data applications/voice-to-clipboard.desktop. Autostart: XDG config
`autostart/voice-to-clipboard.desktop`; один механізм, без паралельного systemd service.
Перевір on/off через logout/login. Старі desktop bindings, які запускають `dictate`,
не треба дублювати native host shortcuts: прибери конфлікт або обери інші modifiers.
На Wayland tray copy-recording працює; global shortcuts — через desktop settings,
автовставка лишається manual fallback як у C.

## Відкат

Спочатку Quit app і вимкни Start at login. Прибрати свої launchers:

```powershell
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app --uninstall
```

Потім можна переключити main і перевстановити `.[whisper,hotkeys]`.
Не видаляй venv, поки його шлях прописаний в автозапуску. Історія/моделі/налаштування
не видаляються командою uninstall launchers.

## Що надіслати

```text
Commit / ОС / Python / CPU або CUDA або M4:
Автотести / desktop smoke:
Start Menu або .app/.desktop / без консолі:
Tray/menu та settings panel:
U/E/L / start-stop з меню / 20 записів:
Pause/Resume / settings / invalid-conflict rollback:
Singleton (повторний запуск):
Autostart ON → login / OFF → login:
Quit idle / recording / transcribing / Cancel / PID cleanup:
System check / log / error recovery:
Uninstall launcher / повторний install:
FAIL: кроки, очікування, факт, технічна помилка без приватного тексту.
```

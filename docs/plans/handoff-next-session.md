# Передача контексту та робочий процес до першого релізу

Оновлено: 2026-09-26. Це знімок для нового чату, а не заміна актуального git/CI.
Єдиний план вимог і виконання: [desktop-experience-roadmap.md](desktop-experience-roadmap.md).

## Остання прийнята й змерджена поставка — E.1 packaging spike

Гілка `codex/packaging-spike`, база `27add90`. PyInstaller onedir, explicit child
routing, ізольований frozen Qt/native imports/worker IPC probe, Windows/macOS ARM64
workflow. Код `70844b7`; Source suite: 104 tests OK, 4 skips; native Linux lifecycle OK.
[Frozen CI 36168009284](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36168009284):
Windows x64/macOS ARM64 успішні, включно з overlay pipe/EOF і frozen desktop lifecycle.
[Regression CI 36168009450](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36168009450):
усі 6 jobs успішні. Windows 376 MB, macOS 1.15 GB; подробиці таймінгів у звіті.
Bundler: PyInstaller onedir. Windows-приймання отримано 2026-09-26: користувач
підтвердив усі ручні пункти; локальний probe на Windows 11 AMD64 build 26200
успішний (worker/overlay OK, Qt 4.185 s, in-process probe 6.568 s).
Наданий Windows Server JSON — CI artifact, не локальний результат.
Окремого model/device протоколу optional voice test не надано.
Користувач повторно прийняв сценарії й дозволив merge/push/delete 2026-09-26.
Сфокусоване pre-merge review не знайшло блокувальних дефектів; код не змінено.
Після перевіреного `70844b7` лише docs, повторних тестів не запускали.
Merge `7ba73b2` у main запушено; `origin/codex/packaging-spike` видалено.

Наступна конкретна задача — **E.2 Windows per-user CPU installer** від актуального
main: встановлення без Python/Git/CUDA, Start Menu, один керований автозапуск,
upgrade/uninstall/reinstall зі збереженням profiles/settings/history.
Приймання: чиста Windows VM, launch/CPU dictation/Quit, upgrade, login startup,
uninstall/reinstall; version/checksum і явний signing status. Чинні Settings та
source path зберегти; нових продуктових функцій не додавати. Installer tooling
обрати в E.2. macOS DMG, Linux package і NVIDIA runtime — окремі поставки.
E.2 реалізовано в `codex/windows-cpu-installer` від `60f8d91`: Inno per-user CPU
installer, stable HKCU startup, mutex, data preservation, metadata/checksum.
[Команди й ручне приймання E.2](../setup/windows-installer.md). Код `3397697`: [installer CI](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36235750191)
і [6-job regression CI](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36235750202)
успішні; локально 106 tests OK, 4 skips. Installer 0.1.1 unsigned, artifact містить
checksum/build-info; lifecycle/data preservation і synthetic tiny.en CPU inference
перевірено на Windows Server 2025 runner. Виправлено test-only uninstaller path
після rapid reinstall. Наступна дія — чиста Windows 10/11 CPU voice/login/manual
acceptance E.2; merge не виконано. Не починати E.2 повторно.
Не позначати hardware/voice/clean-machine gates завершеними.
[Звіт і команди](../setup/packaging-spike.md).

## Остання прийнята поставка — D.2b Settings redesign

Реалізовано в `codex/settings-redesign` від актуального `origin/main` `bc60d3c`.
Qt Settings замінює Tk panel: Languages, пошук, один Save/Cancel, inline errors,
General/Advanced з окремими partial saves та існуючий first-run. Host/core/schema,
tray/hotkeys/guarded paste не переписані; production UI не зберігає settings напряму.
Research-гілку D.2a не переносили. PySide6 додається тільки до desktop extra.

Локально: 99 tests OK (4 platform skips), Qt native Linux smoke, tray/host lifecycle
з singleton, pause/resume і 5 restart/Quit; offscreen scale 100/150/200%, light/dark
renders, keyboard/accessibility names. Без voice/GPU/download. Фізичні
hardware matrix та screen reader відкриті. Користувач 2026-09-25 підтвердив
перелічені сценарії та дозволив merge/push/delete branch; ОС цього повтору
окремо не зазначена, повну hardware matrix це не закриває.

Код: `dc1d720`; Linux Qt runtime follow-up: `b5aab52`.
[CI `36128646652`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36128646652)
успішний на всіх 6 jobs (Windows/macOS/Linux × Python 3.11/3.12), включно з
native Qt/lifecycle, Windows paste і масштабуванням. Перший Ubuntu CI впав через
відсутню libEGL; системні залежності додані до CI та інструкції встановлення.

Сфокусоване pre-merge review не виявило блокувальних дефектів; код не змінювався.
Merge: `f9c3236`, main запушено, `origin/codex/settings-redesign` видалено.

Наступною після D.2b була **E.1 packaging spike**, тепер реалізована вище:
frozen Qt app, worker spawning і native dependencies на Windows CPU та Mac ARM64;
size/cold start, вибір bundler та support matrix перед installers. Нових features
не додавати. Актуальний стан E.1 і наступна дія наведені на початку handoff.

## Локальне розташування після перенесення

- Репозиторій і наявний venv: `/home/artem-trybushenko/Projects/voice-to-clipboard`.
- Особисті data/history/settings/backups: `~/.local/share/dictate` (чинний data path).
- `~/.local/bin/dictate` посилається на новий код і CUDA libraries; GNOME bindings
  U/E/L не змінені. Кеші/моделі не переносились і не видалялись.
- Резервна копія даних/launcher/bindings: `~/.local/share/dictate/backups/relocation-2026-09-25`.
- Дані перевірено побайтово до/після перенесення. Python package перевстановлено
  з нового шляху без зміни speech/CUDA dependencies; launch/isolated regression
  перевірки наведені в delivery guide.

[Точні команди оновлення та короткий тест](../setup/settings-redesign.md).
Старі записи нижче — історія; нову реалізацію D.2b не починати повторно.

## Остання завершена поставка — D.1 first-run у Settings

Реалізація `8f192b1`, база `e9be15c`; merge у `main`: `1a6e23c`, 2026-09-23.
Main запушено; remote-гілку `codex/first-run-settings` видалено після push.
Для оновлення використовувати `main`: [команди й ручний тест](../setup/first-run.md).

Результат: English guidance та Finish setup and apply; optional
`onboarding_complete` зберігається лише в успішній settings transaction.
Наявні prefs/history не переписуються при старті; чиста установка запам'ятовує
тільки English preset без completion. Перерваний setup відкривається знову,
завершений — ні. Старий host потребує Quit/relaunch перед Apply.

Докази:
- 98 local tests OK (4 platform skips), включно з validation/registration/write
  failures, збереженням completion і bytes, schema v2/v3 та clean-history regression.
- Real Tk: interrupted/failed/resumed/completed setup, Finish/close, model feedback,
  malformed reply recovery та Quit. Native Linux: auto-open до completion,
  відсутність після completion, persistence та 5 restart/Quit. Ізольовані дані.
- [CI `8f192b1`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35830338650):
  усі 6 jobs Windows/macOS/Linux × Python 3.11/3.12 успішні.
- Користувач підтвердив перелічені ручні сценарії 2026-09-23 та дозволив merge,
  push і видалення remote-гілки. Це не окремий протокол усієї hardware matrix.
- Перед merge переглянуто completion, Apply/rollback, startup і сумісність settings;
  блокувальних дефектів не виявлено. Функціональний код не змінено, тести повторно
  без нових змін не запускали; наведені локальні результати — з реалізації поставки.

Обмеження: unsaved edits не відновлюються; GTK без tray host відкриває control
panel навіть після completion. Offline model check не гарантує custom repo,
backend format або inference. Mic/model download/GPU, фізичний macOS/M4 та
clean-machine release gates цією поставкою не закриті.

## Уточнений напрям після перегляду D.2a — 2026-09-25

Research-гілка `codex/desktop-ux-prototype` була створена від актуального
`main` `6827399`, але не переноситься в `main`: вона містить прототип і
відхилений product scope.

Власник прийняв лише технічний напрям Qt/PySide6 і ціль зробити Settings
сучасним. Він не прийняв розширення продукту: Draft, templates, context import,
нові workflows, AI/LLM, integrations, нові delivery modes або нове сховище.
Voice to Clipboard лишається наявним flow: shortcut → voice → clipboard або
guarded paste. Ці обмеження є авторитетними для всіх наступних поставок.

D.2a — ізольований технічний прототип. Його Draft tab і симульовані
download/doctor-сценарії не є acceptance і не база для production UI. D.2b
починається чистою гілкою від `main`; для нього повторно перевіряються keyboard
accessibility, Windows/macOS manual і frozen packaging у відповідних поставках.

**Історичне формулювання поставки (тепер реалізована вище) — D.2b Settings redesign.** Окрема гілка від
актуального `main`: сучасний editor мовних profiles, один Save, inline conflicts,
General/Advanced для вже наявних settings, короткий existing first-run та
сумісність старих даних. Не додавати home screen, recording controls, download
wizard, doctor чи нові product workflows.

Після приймання D.2b — **E packaging/installers**: packaging spike з обраним
Settings UI, Windows installer, macOS ARM64 app/DMG та обраний Linux package,
з update/uninstall/autostart без втрати prefs/history. Потім F clean-machine та
hardware acceptance. Packaging не є попередньою умовою для D.2b.

Відхилені продуктові гіпотези не є backlog і не є джерелом наступних задач.

## Завершена поставка: сумісність моделі й мови

Реалізація `00b5d6d`, база `668f297`; merge у `main`: `50af7cd`.
Користувач 2026-09-23 підтвердив, що всі перелічені ручні сценарії працюють,
і дозволив merge/push та видалення `codex/model-language-compatibility` на origin.
Remote-гілка видалена після push main; для оновлення використовувати `main`.

Результат: editable model lists і English пояснення у Settings; спільний
offline validator блокує відомі несумісні пари до recorder/model load.
Custom models позначені unverified; старі налаштування можна виправити без
автоматичної заміни моделі, втрати overrides або modifiers.

Докази:
- 94 local tests OK (4 platform skips); Tk rejection/custom persistence,
  Apply/Close/Quit та native desktop restart/persistence smoke OK.
- [CI `00b5d6d`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35828213841):
  усі 6 jobs Windows/macOS/Linux × Python 3.11/3.12 успішні.
- Ручне приймання користувача: English-only rejection, сумісна модель після
  restart, custom warning/save, відхилення несумісного inherited default.
- Сфокусований перегляд перед merge: validation/read-repair, запуск recorder,
  Settings Apply; блокувальних дефектів не виявлено. Функціональний код не змінено.

Обмеження: offline metadata не перевіряє існування custom repo, backend format,
download або inference. Реальний голос/GPU, фізичне macOS/M4-приймання та
clean-machine installers цією поставкою не закриті. Приймання користувача
не розширює hardware matrix. [Update/manual test](../setup/model-compatibility.md).

Нижче — історичні знімки попередніх поставок; їхні «наступні задачі» не
перевизначають актуальну задачу вище.

## Завершена поставка: індивідуальні modifiers

Користувач повторно прийняв усі перелічені Windows-сценарії після виправлень
2026-09-23. Merge у `main`: `a91291b`. Додатково успішний
[CI head `fb8d7f5`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35724815235).

Review follow-up: користувач прийняв роботу `1051bbe` на Windows. Review виявив
втрату modifiers при downgrade і macOS 3.12 Quit timeout у CI `35715091939`.
Виправлення: schema v3 (читає v2, старий main відмовляється від v3 до запису),
macOS stop та всі background tray updates поставлено у головну AppKit-чергу.
Повторний CI `35717317966` показав, що лише перенесення stop недостатнє:
pystray setup thread залишався живим після зупинки UI. Коміт `645255b`
прибирає AppKit updates із setup thread; вони більше не блокують його завершення.
Native smoke тепер повторює швидкий restart/Quit п’ять разів і друкує technical
log при збої. Локально: 88 tests OK, 4 skips; Tk smoke і desktop smoke OK;
валідатор попереднього main відхилив новий формат, bytes settings не змінилися.
Smoke readiness також виправлено: чекає відповідь IPC, а не лише socket path
(bind може передувати listen). Фінальний код `50e53c0` пройшов
[CI 35717812820](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35717812820):
усі 6 jobs Windows/macOS/Linux × Python 3.11/3.12 успішні, включно з 5 швидкими
restart/Quit на Windows/macOS. Таймаут Quit не збільшувався.

Гілка `codex/profile-modifiers` створена від актуального `origin/main` `c27e602`.
Реалізовано optional `modifiers` у профілі, редактор у Settings і native bindings
Windows/macOS/X11. Порожній override успадковує default; старі version 2 settings
не змінюють shortcuts. A–Z ключі все ще унікальні. Новий panel перевіряє capability
host, щоб старий resident-процес не втратив override під час Apply.

Локальні докази: 85 regression tests, OK (4 platform skips); окремий Quartz
matching/repeat test, OK; `check_settings_panel.py` з реальним введенням override,
Apply/close/reload, OK; `check_desktop.py` з native registration, Pause/Resume,
restart/persistence і Quit, OK. Усі дані ізольовані; без голосу/моделей.
Windows CI smoke тепер перевіряє конфлікт індивідуального override та rollback.
Windows-приймання базових modifiers отримано; виправлення review перевірено
локально, кросплатформним CI та повторним Windows-прийманням. Merge завершено.
Нижче збережені історичні докази попередньої прийнятої поставки.

Оновлення Windows після повного Quit, у каталозі репозиторію:

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys,desktop]"
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app
```

Ручний протокол: [Individual modifier acceptance](../setup/language-profiles.md#individual-modifier-acceptance).
Наступна конкретна задача D.1 — вибір сумісної моделі у Settings: перевірки
відомих model/language обмежень до запису/завантаження, English пояснення,
збереження custom overrides і restart/persistence. Невідомі custom models
позначати як неперевірені; існуючі налаштування не замінювати мовчки.
Без download wizard, installers і нового onboarding у цій наступній поставці.
У цьому чаті її реалізацію не починали.

Обмеження завершеної поставки: унікальні A–Z літери, Wayland manual bindings,
schema v3 потребує сумісного застосунку (downgrade — із резервною копією settings),
фізичне macOS/M4-приймання ще відкрите. Особисті settings/history під час тестів
не змінювалися.

## Мета продукту та незмінні вимоги

Voice to Clipboard — локальний desktop-застосунок для диктування у clipboard або
автовставки в початкове поле. Щоденна робота без термінала: tray/menu bar, глобальні
shortcuts, тимчасовий overlay, автозапуск. Windows, Linux та macOS, особливо Apple M4.

- Жодних LLM для переписування промптів, cloud transcription або надсилання повідомлень.
- Нове встановлення: лише English/E. Інші мови, їх shortcuts і моделі — явний вибір
  користувача. Українська модель чи U/L не повинні нав'язуватись новому користувачу.
- Міграція існуючих установок зберігає налаштування, U/E/L та історію; видалені профілі
  не відновлюються самі. Користувацький transcript не перекладати.
- UI, CLI help, diagnostics та власні технічні логи англійською. Розмова з власником — українською.
- Idle не записує мікрофон. Оверлей не забирає фокус. Paste захищає початкове поле;
  невизначений/змінений target → clipboard + зрозуміла причина, не вставка навмання.
- Логи не містять transcript/audio. Quit/cancel завершує лише власні процеси.

## Репозиторій і стан

- GitHub: https://github.com/trybushenko/voice-to-clipboard (public).
- Локальний checkout: `/home/artem-trybushenko/Projects/voice-to-clipboard`.
- Python package: `src/voice_to_clipboard`; tests: `tests`; helpers: `scripts`.
- Linux development venv: `venv/bin/python`; Windows приклади: `.venv\Scripts\python.exe`.
- Main містить прийняті A/B/C/D, актуальний source onboarding і English messaging.
  Відомий merge main: `100ebd5` (перевірити, чи не з'явилися нові коміти).
- D.1 Language Profiles та Windows lifecycle fixes прийняті користувачем на
  Windows 2026-09-22 і змерджені в `main`; функціональну remote-гілку видалено.
- Останній функціональний код поставки: `c368776`; завершальне документаційне
  рев’ю: `2e0276a`.
- Інші завершені remote-гілки прибрані. Перевірити реальний remote перед наступними діями.
- Не плутати це приймання D.1 з незавершеними E/F: installers, hardware matrix,
  first-run wizard та незалежні modifiers усе ще окремі поставки.

## Що вже зроблено у D.1

English runtime messages змерджені. У гілці профілів реалізовано:

- Version 2 settings та міграція; нові користувачі мають English/E clipboard.
- Add/Update/Remove профілю: мова, A–Z літера, clipboard/paste, model override.
  Модифікатори зараз спільні для всіх профілів; незалежні комбінації ще не зроблені.
- Tray/native registrations відображають тільки обрані профілі. Settings відкривається
  при першому запуску. Повні English names усіх 100 мов, alphabetical dropdown.
- Multilingual `large-v3-turbo` default; явна передача мови/моделі recorder, відхилення
  `.en` моделі для іншої мови. Довільні custom repositories повністю не перевіряються.
- Apply acknowledgment, захист від close під час save, persistent feedback, live refresh,
  старі host responses більше не зупиняють poll loop. Закриття Settings ≠ Quit tray app.
- Виправлено відтворений Windows Tk crash `Tcl_AsyncDelete`: worker передає callback IDs,
  GUI callbacks залишаються у UI thread; shutdown очікує завершення worker.

## Приймання D.1 і наступна конкретна дія

Користувач розгорнув GitHub-гілку на Windows 2026-09-22 і підтвердив, що Language
Profiles працюють чудово. Це приймає профілі, hotkeys, Apply/close, Quit і paste
для його сценарію. Focus guard залишається увімкненим: відмова при дійсній зміні
поля все ще є правильною поведінкою.

Наступна поставка має бути однією обмеженою незакритою частиною D.1: незалежні
modifiers для кожного профілю **або** простий first-run/model onboarding — не
обидві одразу. Packaging rewrite не починати без окремого рішення.

## Завершення сфокусованого рев’ю 2026-09-22

Рев’ю `main...9304704` перевірило тільки збереження профілів, Apply/close,
належність Tk callbacks UI-потоку, Quit, реєстрацію/rollback hotkeys та remote
paste guard. Доведеного дефекту не знайдено; функціональний код не змінювався.
Профіль зберігається лише після успішної реєстрації, Close чекає Apply, worker
передає тільки ID callback, Quit не перетворює закриття Settings на непередбачуване
завершення, а child перевіряє paste token в оригінальному host і не захоплює нову
ціль.

Локально пройшли 34 релевантні unit-перевірки. Один тест round-trip
`ControlServer` не зміг bind Unix socket в поточному sandbox (`PermissionError`),
отже не є негативним результатом застосунку; його вже покриває попередній
кросплатформний CI. Це не замінює Windows-приймання і не доводить причину
конкретної відмови paste.

### Короткий Windows-протокол повторного приймання

У PowerShell відкрийте каталог репозиторію. Спочатку повністю закрийте старий
host (не лише Settings):

```powershell
cd C:\path\to\voice-to-clipboard
.\.venv\Scripts\voice-hotkeys.exe --quit
```

Дочекайтеся, поки tray icon зникне. Оновіть саме гілку профілів і перевстановіть
пакет:

```powershell
git switch codex/language-profiles
git pull --ff-only origin codex/language-profiles
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys,desktop]"
git rev-parse --short HEAD
```

Для приймання без змін у ваших settings/history запустіть ізольоване вікно
застосунку (PowerShell залиште відкритим, доки не завершите тест):

```powershell
$vtcAcceptance = Join-Path $env:TEMP ("vtc-accept-" + [guid]::NewGuid())
$env:VOICE_TO_CLIPBOARD_DATA_DIR = Join-Path $vtcAcceptance 'data'
$env:VOICE_TO_CLIPBOARD_CACHE_DIR = Join-Path $vtcAcceptance 'cache'
New-Item -ItemType Directory -Force -Path $env:VOICE_TO_CLIPBOARD_DATA_DIR, $env:VOICE_TO_CLIPBOARD_CACHE_DIR | Out-Null
Start-Process -FilePath .\.venv\Scripts\python.exe -ArgumentList '-m','voice_to_clipboard.ui.desktop_app','--run'
```

Очікувано: з’являється tray icon і Settings; у чистому профілі є тільки English/E.
Додайте `Polish (pl)`/`P` і `Indonesian (id)`/`I`, натисніть **Apply all settings
and profiles** і дочекайтеся **Saved and active**. Закрийте/відкрийте Settings,
потім зробіть tray **Quit (finish dictation first)** і запустіть ту саму ізольовану
команду ще раз: обидва профілі та shortcuts мають зберегтися. Видаліть один
профіль, Apply, Quit/relaunch: він не повертається і його letter більше не
зареєстрований. Перевірте Apply і негайний Close; у разі registration failure
старі shortcuts і збережені settings лишаються активними. Перевірте Quit у станах
idle, recording і transcribing.

Для paste: із закритим Settings поставте caret у звичайному не-pідвищеному
редакторі, використайте профіль з **Paste with hotkey**, продиктуйте короткий
нешкідливий тест. Без зміни фокусу очікується вставка; після навмисної зміни поля
очікується відмова і текст тільки в clipboard. Не послаблюйте guard заради цього
тесту. Після закриття ізольованого app за потреби виконайте automated smoke
(вони використовують тестові дані; paste checks тимчасово замінюють clipboard):

```powershell
.\.venv\Scripts\python.exe scripts/check_settings_panel.py
.\.venv\Scripts\python.exe scripts/check_desktop.py
.\.venv\Scripts\python.exe scripts/check_paste.py --auto --overlay --remote-host
.\.venv\Scripts\python.exe scripts/check_paste.py --auto --change-focus --remote-host
```

Якщо щось не спрацює, надішліть повний новий English-text помилки, short commit,
Windows edition/build, `python --version`, редактор і чи він elevated, profile
language/key/modifiers/delivery, точну послідовність фокусу й чи вставився текст
у clipboard. Також надішліть технічний log з
`$env:VOICE_TO_CLIPBOARD_DATA_DIR\logs\desktop.log` (без history/transcript).
Не надсилайте transcript або audio.

## Докази перевірок

- Local suite: 82 tests, OK, 4 platform skips.
- Real local GUI smoke: Add/Apply/close, malformed response recovery, Quit;
  native desktop smoke перевіряє збереження після нового процесу.
- Успішний CI коду `c368776`: https://github.com/trybushenko/voice-to-clipboard/actions/runs/35637032624
  Windows/macOS/Linux × Python 3.11/3.12, усі 6 jobs; Windows native paste через RemoteGuard IPC.
- Фізичний M4, clean-machine installers та user-specific останній paste failure не закриті.
- Не запускати всі перевірки повторно тільки заради відновлення контексту.

Команди (після релевантних змін; GUI tests потребують графічної сесії):

```sh
PYTHONPATH=src venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src venv/bin/python scripts/check_desktop.py
PYTHONPATH=src venv/bin/python scripts/check_settings_panel.py
```

Windows з актуально встановленим пакетом:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/check_desktop.py
.\.venv\Scripts\python.exe scripts/check_settings_panel.py
.\.venv\Scripts\python.exe scripts/check_paste.py --auto --overlay --remote-host
.\.venv\Scripts\python.exe scripts/check_paste.py --auto --change-focus --remote-host
```

Paste tests замінюють clipboard тестовим текстом. Smoke tests не перевіряють реальний голос/GPU.
Перед pip update завершити диктування і Quit увесь app, не тільки панель Settings.

## Карта коду для діагностики

- `core/profiles.py`, `core/desktop_settings.py`, `core/settings.py`: validation/migration/save.
- `ui/desktop_panel.py`: Tk editor, async queues, callback ownership, Apply/close/poll.
- `ui/desktop_app.py`: tray, singleton, запуск/закриття panel та resident host.
- `ui/hotkeys.py`, `core/host_control.py`: registrations, generation, settings transaction, IPC.
- `core/hotkey_session.py`: owned recording/model processes, language/model, paste token.
- `platform/focus.py`: local/remote guard; `platform/windows_hotkeys.py`: RegisterHotKey.
- `tests/unit/test_profiles.py`, `scripts/check_settings_panel.py`, `scripts/check_desktop.py`,
  `scripts/check_paste.py`: ключові regression сценарії.

## Порядок до завершеного продукту

1. D.2b Settings redesign: сучасні Languages, один Save, inline conflicts,
   General/Advanced для існуючих settings та короткий наявний first-run.
   Не змінювати щоденний диктувальний flow і не додавати product features.
2. Приймання D.2b: English і неанглійський profile, shortcut/delivery, conflict,
   Cancel, restart, звичайне copy/paste; перевірки доступності та сумісності.
3. E packaging spike: frozen build з прийнятим Settings UI, worker spawning і
   native dependencies на Windows CPU та Mac ARM64; записати support matrix.
4. E installers: Windows per-user runtime bundle, macOS ARM64 app/DMG, обраний Linux package;
   update/uninstall/autostart без втрати prefs/history. Використати D.2b Settings,
   не створювати download wizard або doctor. Signing/notarization чесно позначити.
5. F release: clean Windows без Python/Git/CUDA, Ubuntu, фізичний M4; NVIDIA окремо;
   regressions і довгі сесії; artifacts/version/checksums/release notes/known limitations.

## Definition of done для першого публічного релізу

Людина, яка не знає української й не є розробником, знаходить репозиторій,
встановлює підтримуваний artifact, проходить English onboarding, налаштовує власну
мову/shortcut, отримує текст у clipboard/paste та користується після login без термінала.
CPU шлях працює без CUDA. Помилки ведуть до конкретної дії. Settings/update/uninstall
не гублять дані. На кожній заявленій підтримуваній платформі є доказ перевірки;
неперевірені платформи/функції явно позначені, а не видані за стабільні.

## Як працювати короткими чатами

Один чат — одна обмежена поставка з roadmap. Не копіювати всю історію. На старті
прочитати цей handoff, релевантний розділ roadmap, git status/diff та відповідні файли.
На завершенні оновити ці документи: branch/commit, що зроблено, докази, відкриті
помилки, наступна дія. Реалізація, CI, ручне приймання та merge — різні статуси.

Review потрібне перед merge функціональних змін: concrete bugs/regressions, file/line,
severity і missing checks; не стилістичний rewrite. Для перекладів/документації
не вимагати окремого ручного приймання без причини. Обсяг тестів пропорційний ризику.
Не створювати паралельні гілки без потреби; після merge видаляти завершену remote-гілку.
Не змінювати особисті settings/history під час тестів: використовувати ізольовані data/cache.

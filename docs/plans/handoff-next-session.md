# Передача контексту та робочий процес до першого релізу

Оновлено: 2026-09-22. Це знімок для нового чату, а не заміна актуального git/CI.
Єдиний план вимог і виконання: [desktop-experience-roadmap.md](desktop-experience-roadmap.md).

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
- Локальний checkout: `/home/artem-trybushenko/.local/share/dictate`.
- Python package: `src/voice_to_clipboard`; tests: `tests`; helpers: `scripts`.
- Linux development venv: `venv/bin/python`; Windows приклади: `.venv\Scripts\python.exe`.
- Main містить прийняті A/B/C/D, актуальний source onboarding і English messaging.
  Відомий merge main: `100ebd5` (перевірити, чи не з'явилися нові коміти).
- Активна незмерджена гілка: `codex/language-profiles`.
- Останній код перед handoff: `c368776`; документована ревізія: `8f09b5f`.
- Інші завершені remote-гілки прибрані. Перевірити реальний remote перед наступними діями.
- Гілку профілів **ще не прийнято після останніх виправлень Windows**. Не плутати
  прийняті B/C/D з прийманням нової функціональності D.1.

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

## Незакритий фідбек і наступна конкретна дія

Користувач повідомляв: нові мови зникають, shortcuts не працюють; Quit потребує
зайвого кліку; L дає `host unavailable` / `original paste target changed`.
Останні зміни виправляють lifecycle/UI; старий resident host після pip-update —
правдоподібна причина несумісності, але НЕ доведена причина всіх помилок на його ПК.

Потрібно повторне Windows-приймання після повного Quit → update → relaunch:

1. Polish/P, Indonesian/I → Add → Apply → Saved and active.
2. Закрити/відкрити Settings; потім Quit у треї та новий запуск. Профілі й hotkeys збережені.
3. Видалити профіль, Apply, restart: він не повертається, shortcut звільнено.
4. Apply і негайний close; помилка registration; repeated Apply; Quit idle/recording/transcribing.
5. Автовставка з редактора, Settings закрито; зміна поля повинна й надалі блокувати paste.
6. При відмові отримати ПОВНИЙ новий текст помилки, ОС/Python/commit, редактор,
   shortcut/modifiers, момент зміни фокусу; технічний log без приватної history.

Не вимикати focus guard, щоб приховати paste-помилку. Не заявляти про її повне
усунення лише за CI. Якщо фідбеку ще немає — виконати сфокусоване code review
`main...HEAD`, усунути доведені дефекти та підготувати короткий manual protocol.
Не починати великий packaging rewrite до стабілізації цієї поставки.

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

1. Стабілізувати/прийняти поточну D.1-поставку; review, targeted tests, Windows acceptance.
   Після дозволу користувача: merge main, позначити факти у roadmap, прибрати remote-гілку.
2. Закрити залишок D.1 окремими поставками: незалежні hotkey modifiers, простий first-run
   сценарій, зрозумілий вибір сумісної моделі. Не робити два різних onboarding wizard.
3. E packaging spike: перевірити bundler/native libraries/worker spawning у frozen build,
   Windows CPU та Mac ARM64; записати рішення і support matrix до масових installers.
4. E onboarding/doctor: real backend inference, модель/download progress/cancel/retry,
   permissions/microphone, диск/мережа/offline, зрозуміла дія відновлення; GPU необов'язковий.
5. E installers: Windows per-user runtime bundle, macOS ARM64 app/DMG, обраний Linux package;
   update/uninstall/autostart без втрати prefs/history. Signing/notarization чесно позначити;
   сертифікати є зовнішньою залежністю. Нині існує тільки source/pip installation.
6. F release: clean Windows без Python/Git/CUDA, Ubuntu, фізичний M4; NVIDIA окремо;
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

# План: надійне диктування без термінала на Windows, macOS і Linux

Для нового чату: [handoff і порядок до релізу](handoff-next-session.md)
(ревізія 2026-09-26). Мовні профілі та індивідуальні modifiers прийняті й
змерджені (`c27e602`, `a91291b`). Сумісність мови й моделі прийнята користувачем і змерджена (`50af7cd`).
D.1 first-run прийнято користувачем і змерджено: `1a6e23c` (код `8f192b1`).
D.2a реалізовано окремо в `codex/desktop-ux-prototype` від актуального main
`6827399`; його code/prototype не переноситься в `main`. Після перегляду
2026-09-25 власник звузив scope: потрібен лише сучасний UI/UX **Settings** для
наявного Voice to Clipboard. Draft, templates, context import, нові workflows,
нові delivery modes та інші функції не прийняті. D.2b прийнято користувачем 2026-09-25 та змерджено в `main`: `f9c3236`
(код `dc1d720`, CI follow-up `b5aab52`). E.1 packaging spike реалізовано й автоматично перевірено в `codex/packaging-spike`
(код `70844b7`); прийнято користувачем і змерджено 2026-09-26: `7ba73b2`.
Main запушено, завершену remote-гілку видалено. Далі E.2 Windows per-user CPU installer; звіт E.1 унизу.

Початковий план: 2026-09-14, база `072172a`. Ревізія A/B/C: 2026-09-15,
після `1d545b0`, робоча гілка `codex/windows-hotkeys-paste`.

**Статус: A завершено; B/C прийняті користувачем на Windows 2026-09-17
після focus/overlay виправлень і дозволені до merge в main. Фізична macOS
матриця залишається відкритою. D прийнято користувачем на Windows 2026-09-18 і дозволено до merge в main.
Обмежені D.1-поставки прийняті та змерджені; D.2a дала технічний напрям, але
не є acceptance нового продуктового функціоналу. D.2b прийнято й змерджено. E.1 прийнято й змерджено; далі E.2 Windows installer та решта E/F.**

Позначення: `[x]` — конкретна реалізація або перевірка, для якої є доказ;
`[ ]` — відсутня реалізація чи непроведена перевірка. Код і ручне приймання
позначаються окремо. Зелений CI не дорівнює перевірці мікрофона/caret/фокусу.

| Етап | Що вже є | Що залишилось | Доказ |
| --- | --- | --- | --- |
| A | src package, тести/скрипти/docs, wheel, сумісний launcher | Немає відкритих робіт A; tray/setup/packaging — D/E | `69d97a8`, [звіт A](stage-a-verification.md) |
| B | Ізоляція worker, retry/atomic IPC, Ctrl+C/drain/cancel; тепер також CLI pause/resume/status/stop/quit | Background/control реалізовані; фізичні Windows/macOS перевірки — gate | `9f63f2d`, `905c1a6`, Windows-фідбек користувача, [звіт B](stage-b-progress.md) |
| C | Нативні hotkeys, SendInput, modifiers/settings, захист вставки, result overlay | Ручна матриця Windows/macOS; Wayland — явно manual fallback | `1d545b0`, 6 CI jobs, [звіт C](stage-c-verification.md) |

[Повна ревізія A/B/C і доробки](abc-audit.md). Документ покриває всі 8 пунктів
початкового Windows-фідбеку; не всі вони належать до A/B/C.

## 1. Яким має бути результат

Користувач установлює **Voice to Clipboard** звичайним способом, проходить коротку
перевірку мікрофона й дозволів та вмикає «Запускати при вході». Після наступного
входу в систему браузер, VS Code чи інший застосунок уже можуть бути відкриті:

- `Alt+Shift+U`: запис українською → повторне натискання → текст у буфері.
- `Alt+Shift+E`: аналогічно англійською.
- `Alt+Shift+L`: українською → текст у буфері та вставка в поле, де стоїть курсор.
- Жодних зайвих `L`, `U`, `Л`, `Ю`, перемикань фокусу чи вікон консолі.
- Невеликий оверлей показує запис/обробку та зникає після завершення.
- Іконка в системному треї / menu bar: стан, призупинення хоткеїв, налаштування,
  перевірка системи, журнал помилок і «Вийти».
- Після «Вийти» мікрофон закритий, хоткеї звільнені, оверлей прибраний,
  процеси цього екземпляра завершені. Наступний ручний запуск працює нормально.
- Фоновий застосунок слухає **комбінації клавіш**, а не постійно записує мікрофон.

Додавання команди до PATH — лише зручність для CLI. Постійна доступність потребує
користувацького автозапуску/агента. CLI залишається для діагностики й розробки,
але не є обов'язковим щоденним сценарієм.

Зберегти наявні комбінації. Згадку Ctrl у пункті 6 не трактувати як запит змінити
їх усі: додати можливість переналаштування та перевірку конфліктів.

## 2. Поточний стан за початковим фідбеком

Шляхи нижче відносні до `src/voice_to_clipboard/`, якщо не зазначено інше.

| Фідбек | Поточне місце | Результат ревізії | Етап |
| --- | --- | --- | --- |
| 1, 6: без PowerShell | `ui/hotkeys.py`, `pyproject.toml` | Є CLI-host; GUI launcher, tray, installer/autostart ще відсутні | D, E |
| 2: L не вставляє | `platform/windows_input.py`, `platform/focus.py`, `cli.py` | SendInput та перевірки реалізовані; фізична Windows-матриця C ще не підтверджена | C |
| 3: зайві літери | `platform/windows_hotkeys.py`, `macos.py`, `linux.py` | RegisterHotKey / selective tap / passive grabs; реальний X11 smoke пройшов, Windows/macOS manual gate відкритий | C |
| 4, 5: встановлення | `docs/setup/`, extras/backend | Інструкції впорядковані; автоматизації залежностей і installers немає | E |
| 6: Ctrl+C host | `ui/hotkeys.py`, `core/host_control.py` | Керований loop, drain/cancel, окремі pause/resume; GUI-керування ще D | B, D |
| 7: worker/10054 | `platform/processes.py`, `worker/client.py`, `worker/transport.py` | NEW_PROCESS_GROUP/CREATE_NO_WINDOW, retry, atomic endpoint, recovery; користувач підтвердив B на Windows | B |
| 8: структура | `src/`, `tests/`, `scripts/`, `docs/` | Виконано A; runtime history/settings залишаються поза Git | A |

## 3. Послідовність реалізації

Порядок: **відтворення → A → B → C → D → E → F**.
Кожен етап — окремий перевірюваний PR/коміт. Механічне перенесення не змішувати
з виправленням поведінки. Не додавати LLM-форматування, нові моделі заради переписування
тексту чи інші функції поза цим фідбеком.

### Перед змінами: відтворення та діагностична база

- [ ] Зберегти сценарії Windows 10/11: точна команда запуску, версії Python/ОС,
  EN/UK розкладки, режим CUDA/CPU, звичайні чи підвищені права редактора.
- [ ] Відтворити L/U, вставку, Ctrl+C під час запису та під час фінальної транскрипції.
- [ ] Записати тільки технічні події: PID, стан сесії, отриманий hotkey, активне
  вікно, код результату вставки/IPC. Не логувати голос або транскрипт за замовчуванням.
- [ ] Додати regression-тести, які падають на відповідних помилках поточної версії.

### A. Структура репозиторію — P1, фундамент наступних змін

Фактична структура після A і наступних реалізацій B/C:

```text
src/voice_to_clipboard/
  __init__.py, __main__.py, cli.py
  core/       # recording, speech_gate, transcription, history, session,
              # lifecycle, hotkey_session, settings, host_control
  backends/   # faster_whisper, mlx
  worker/     # service, client, protocol, transport, config
  platform/   # paths, desktop, processes, files, focus, windows/input/hotkeys,
              # macos, linux
  ui/         # hotkeys, overlay, terminal
tests/       # unit, integration
scripts/     # benchmark_worker, check_overlay, check_paste, configure-dictation
docs/        # plans, setup, usage, development
.github/workflows/
README.md, pyproject.toml, LICENSE
dictate.py  # сумісна коренева обгортка
```

`dictate.py` — коротка сумісна коренева обгортка. Майбутні `app.py`, tray,
`setup/doctor`, `setup/autostart`, `packaging/` і desktop acceptance suite не
створені як порожні заглушки; це робота D/E/F, а не незавершена міграція A.

- [x] Перейти з `py-modules` на пакет у `src/`, оновити імпорти та запуск worker.
- [x] Зберегти entry points `dictate`, `voice-to-clipboard`, `voice-hotkeys`.
- [x] Залишити коротку сумісну обгортку `dictate.py` для вже налаштованого Linux
  launcher; задокументувати її призначення. Перевірити існуючі desktop bindings.
- [x] Перенести тести, README залишити коротким; деталі інсталяції — у `docs/setup/`.
- [x] Оновити CI, команди benchmark/GUI smoke, шляхи ресурсів у пакеті.
- [x] Не переносити користувацьку історію в Git; зберегти її поточні data paths.

Приймання: wheel установлюється в чистий venv; CLI та тести запускаються з довільної
робочої папки; дочірній worker знаходить пакет; старий Linux-хоткей працює.

Реалізовано 2026-09-15. [Структура й результати перевірок етапу A](stage-a-verification.md).

### B. Життєвий цикл worker, Ctrl+C та IPC — P0

Основна поставка B змерджена в `main` до `905c1a6`. Користувач повідомив, що
описані Windows-сценарії працюють; єдиний наданий збій був у TTY test fixture
і виправлений. Це якісне підтвердження, а не збережена таблиця версій/PID/CUDA.

**Реалізація**

- [x] Спільний process helper: Windows `CREATE_NEW_PROCESS_GROUP`, Unix
  `start_new_session=True`; worker не успадковує Ctrl+C групи диктування.
- [x] Bounded retry/backoff endpoint connect, у тому числі PermissionError;
  sharing violation не видаляє endpoint живого worker і не запускає зайвий процес.
- [x] Атомарний TCP endpoint, bounded file retry/cleanup, lock і локальний token.
- [x] Фрагментовані frames/handshake/stop, EOF/reset/reconnect; retry без дублювання
  підтверджених результатів транскрипції.
- [x] Ctrl+C dictation: stop event → tail → очікування транскрипції → clipboard.
- [x] Ctrl+C host: зупинка приймання hotkeys, bounded listener join, drain дітей;
  повторний Ctrl+C під час drain явно скасовує тільки власні дочірні диктовки.
- [x] Ревізія: окремі `voice-hotkeys --pause`, `--resume`, `--status`,
  `--stop-recording`, `--quit` через приватний IPC. Pause звільняє реєстрації,
  не обриває запис; resume створює новий listener, старі queued actions відкидаються.
- [x] GUI/menu pause/resume/quit — реалізовано в окремій поставці **D**.
- [x] No-console policy: worker/overlay використовують CREATE_NO_WINDOW;
  `voice-hotkeys --background` запускає незалежний host та dictation children.
  Повторний запуск повертає чинний PID; host-журнал без transcript/audio.
  GUI launcher/autostart лишається D, фізичний Windows console-close gate нижче.

**Перевірки й залишок приймання**

- [x] Fake-model subprocess: 20 циклів, незмінний PID, tail, crash/recovery.
- [x] Реальна CUDA на Linux: синтетичний tail після SIGINT, повторне використання.
- [x] Windows-користувач підтвердив описані сценарії B; TTY/non-TTY regression
  виправлено й перевірено в CI.
- [x] Ревізія: Pause/Resume/Status/Stop/Quit перевірені на справжньому X11 host
  з ізольованими settings/cache; control endpoint видаляється після quit.
- [ ] Нові Pause/Resume/control-команди перевірити на реальних Windows/macOS.
- [ ] Окремий деталізований протокол закриття консолі хрестиком, з cold/warm
  worker PID, активним записом і повторним запуском. Повідомлення «все працює»
  не містить цих індивідуальних результатів; не оголошувати CTRL_CLOSE_EVENT вирішеним.
- [ ] Зберегти Windows hardware/версії та окремі результати CUDA/cold/load-stop,
  якщо потрібен повний release-протокол F. `--one-shot` не є заміною worker fix.

[Докази та історія B](stage-b-progress.md).

### C. Хоткеї без зайвих літер та справжня автовставка — P0

**Статус: реалізація та повторне Windows-приймання завершені; користувач дозволив merge.**

**Реалізація**

- [x] Windows RegisterHotKey/WM_HOTKEY + MOD_NOREPEAT, bounded loop, cleanup,
  явні registration conflicts; відсутнє глобальне `suppress=True`.
- [x] Modifiers налаштовуються і зберігаються після успішної реєстрації.
  Ревізія: detection враховує `Hotkey`, `Language Hotkey`, `Layout Hotkey`;
  налаштування розкладки Windows застосунок не змінює.
- [x] Стартовий U/E/L фіксує мову й copy/paste; інший хоткей зупиняє ту саму
  сесію, включно з pending startup, без другого recording process.
- [x] SendInput з коректним pointer-size ABI, перевіркою кількості events,
  bounded очікуванням відпускання modifiers і перевіркою вмісту clipboard.
- [x] Windows UI Automation field/window capture у host; sticky invalidation
  після виявленої зміни, свіжа перевірка перед input, без focus/caret restore.
- [x] Різні статуси copied / paste shortcut sent / fallback; короткий result overlay,
  текст зберігається для ручної вставки. SendInput success не називається GUI success.
- [x] macOS selective Quartz tap, Accessibility/Input Monitoring preflight,
  AX field tracking і Command+V; X11 passive grabs і XTEST без clearmodifiers.
- [x] Wayland capability probe й чесна дія: desktop bindings + manual paste.
- [x] Межа підтримки Wayland визначена: desktop bindings + ручна вставка.
  Portal binding/автовставка не входять до завершеної поставки C; окреме розширення.
- [x] X11: AT-SPI field identity + native focus; sticky focus events виявляють
  програмну зміну поля. Потрібні system Python GI/Atspi; недоступний provider → manual.
- [x] Host утримує початковий focus guard на всіх ОС від старту до завершення child;
  child перевіряє саме його через session token IPC, не обирає новий target.
- [x] Події UIA (Windows), AXObserver (macOS), AT-SPI (X11) доповнюють polling.
  Повної атомарності між фокусом, подіями provider й обробкою Ctrl+V ОС не надає.
  Невизначеність/помилка монітора → clipboard-only, без перенесення фокусу.

**Перевірки й залишок приймання**

- [x] CI базового C `1d545b0`: Linux/Windows/macOS × Python 3.11/3.12,
  включно з native API construction на відповідній ОС.
- [x] Linux GUI: Unicode вставився один раз, фокус збережений; native hotkey
  викликав один callback без сторонньої літери, звичайна U пройшла в поле.
- [ ] Windows: Notepad, Chrome/Edge, VS Code; EN/UK, ліві/праві modifiers/AltGr,
  20 циклів U/E/L, mixed stop, repeat/rapid press, clipboard changes, UIPI.
- [ ] Windows: змінене/закрите поле або вікно, повернення до початкового поля,
  утримані modifiers — переконатися у fallback без випадкової вставки.
- [ ] macOS фізична перевірка event tap, field tracking, permissions та вставки.
- [ ] Linux: перевірка різних DE/XKB layouts та описаного AT-SPI provider fallback;
  Wayland — системних desktop bindings/manual paste, не X11 API.

[Звіт C](stage-c-verification.md) · [Windows-гайд](../setup/windows-stage-c-test.md).
Secure desktop/екран входу не підтримуються. UIPI не обходиться; не вимагати
адміністратора за замовчуванням. Після manual acceptance оновити конкретні рядки,
а не весь етап одним чекбоксом.

### D. Desktop-застосунок, tray та автозапуск — P1

Реалізація у `codex/desktop-tray-autostart`; Windows-приймання підтверджене
користувачем 2026-09-18. Фізичні macOS M4/Linux DE перевірки залишаються окремими. [Звіт D](stage-d-verification.md) ·
[Desktop testing guide](../setup/desktop-stage-d-test.md).

- [x] Єдиний користувацький процес: tray/menu bar, hotkeys, controller сесій, IPC;
  окремий worker для розпізнавання. Мікрофон відкривається лише під час запису.
- [x] Стани: idle → recording → transcribing → delivered/error → idle;
  disabled та shutting-down обробляються явно. Один активний запис.
- [x] Пункти tray: почати/завершити, пауза хоткеїв, копіювати останнє, налаштування,
  перевірити систему, відкрити журнал, автозапуск, вийти.
- [x] Windows: GUI launcher/Start Menu shortcut, користувацький автозапуск при вході
  (обрати один механізм: Startup shortcut або HKCU Run). Не Windows Service у Session 0.
- [x] macOS: `.app`, menu bar, login item або LaunchAgent користувача.
  Підпис/notarization та стабільний bundle ID врахувати для дозволів після оновлення.
- [x] Linux: `.desktop` і XDG Autostart; за потреби systemd --user з коректною
  прив'язкою до графічної сесії. Не тримати одночасно два механізми автозапуску.
- [x] Повторний запуск відкриває стан чинного екземпляра, а не другого слухача.
- [x] App Exit звільняє hotkeys, microphone, власний worker, locks, panel і overlay:
  до 120 секунд drain, потім cancellation лише owned processes.
  Вимкнення автозапуску з GUI має бути перевіреним зворотним шляхом.
- [x] CLI доступний через user PATH за бажанням, а developer setup `--install` створює launcher paths
  самостійно; bundled installer — E. No-console host збирає structured technical events у файл з ротацією,
  без transcript/audio; довільний stderr не записується як користувацький текст.

Приймання: установити → ввімкнути автозапуск → sign out/sign in → не відкриваючи
термінал надиктувати U/E/L із браузера та VS Code. Закрити всі термінали — застосунок
працює. Pause/Resume/Exit та повторний запуск не залишають zombie-процесів.

### Поточна черга виконання — ревізія 2026-09-21

Цей документ — єдине джерело статусу. Детальні вимоги D.1/E/F нижче;
черга тут визначає порядок поставок, а не замінює їхні acceptance criteria.

**Зафіксований результат**

- [x] A: структура пакета, tests/docs/scripts та сумісні точки входу.
- [x] B/C: Windows worker, lifecycle, hotkeys та guarded paste; прийнято користувачем.
- [x] D: desktop/tray, settings, autostart, shutdown; прийнято користувачем;
  merge у main `9347285`. Фізичний M4 та повна Linux DE матриця ще відкриті.
- [x] README та source onboarding англійською для актуального main, ZIP без Git,
  first recording, startup, troubleshooting/update/uninstall: `ee67444`.
  Це документація, не підтвердження clean-machine installation.
- [x] Частковий English CLI/GTK переклад реалізовано: `f3a3333`, 74 тести OK
  (4 platform skips). Аудит завершено у `d54e1e2`; користувач дозволив merge
  без окремого ручного приймання текстових змін.
- [x] Remote прибрано: merged B/C і D branches видалено. Залишені `main` та
  `codex/english-cli-messages` з незмердженою частиною D.1.

**Послідовність поставок: 1–3 завершені, 4–6 актуальні**

| № | Робота | Критерій завершення |
| --- | --- | --- |
| 1 | Завершити English-аудит у поточній `codex/english-cli-messages`: notifications, model/worker, clipboard, overlay, CLI та diagnostics | Усі власні user-facing рядки англійською, без перекладу transcript; тести, CI, перевірка помилок/індикатора; приймання → merge → видалення гілки |
| 2 | D.1 profiles: versioned settings schema, migration U/E/L, language/model compatibility, повні shortcuts і delivery | Старі prefs збережено; Polish/English/Ukrainian профілі; duplicate/conflict validation, atomic save та rollback; pause/restart/paste без регресій |
| 3 | D.1 first-run UI та редактор профілів | Новий користувач обирає мову, shortcut і copy/paste без редагування файлів; existing users не втрачають конфігурацію; польськомовний тестувальник проходить сценарій |
| 3a | D.2a UX-прототип і перевірка UI-технології | Виконано як дослідження; лише Settings-напрям і Qt decision переходять далі. Draft та інші розширення відхилені |
| 4 | D.2b Сучасний Settings UX | Зручне налаштування мовних профілів, shortcut і clipboard/paste; наявні функції, дані та поведінка диктування збережені |
| 5 | E packaging spike і installers | Пробні frozen builds, потім Windows installer, macOS ARM64 app/DMG та обраний Linux package; update/uninstall/autostart без втрати даних |
| 6 | F release acceptance | Clean Windows без Python/Git/CUDA, Ubuntu та фізичний M4; GUI/paste/permissions/login, NVIDIA окремо, довгі сесії; version/checksums/release notes і відомі обмеження |

Історичний порядок: кроки 1–3 реалізовані та прийняті в межах описаних поставок;
D.2a реалізовано; 2026-09-25 scope звужено до Settings UX. Далі кроки 4–6.
Для кроків 2–3 спочатку спроєктувати schema/migration та спільне model-language
mapping; не зашивати нові мови в окремі копії U/E/L-команд. Кожну поставку вести
в одній активній гілці від актуального main; завершені гілки прибирати після merge.
F-тести додавати під час відповідної реалізації, фінальний gate — на release artifacts.

**Як підтримувати статус під час роботи**

- В одному коміті з реалізацією оновлювати відповідний пункт цього документа:
  зроблене, commit/branch, перевірки та що лишилося. `[x]` ставити лише за доказом.
- Відрізняти «код готовий», «CI успішний», «перевірено користувачем» і «змерджено».
  Зелений CI не закриває physical hardware/login acceptance.
- Після кожної поставки оновлювати README/installation, якщо змінився user flow;
  залишати короткий test guide і наступну конкретну дію.
- Не включати LLM rewriting, cloud transcription чи автоматичне надсилання тексту.

### D.1. International onboarding — наступна окрема поставка

Заплановано 2026-09-18 за фідбеком користувача та польського тестувальника.
Це новий scope, не незавершена частина прийнятого D. Почати в окремій гілці.

Часткова поставка 2026-09-21: `codex/english-cli-messages` перекладає CLI help,
calibration, recording/delivery notifications, terminal meter та GTK overlay
англійською. Це лише текстові зміни: мови transcript, defaults та shortcuts
не змінені. Перевірено CLI `--help` і regression suite (74 тести, 4 platform skips).
Повний аудит інших модулів завершено у `d54e1e2`. Configurable profiles і
first-run flow залишаються відкритими; весь D.1 не позначено завершеним.

- [x] README/setup source onboarding англійською оновлено в main (`ee67444`).
- [x] Власні UI, tray, CLI/help, progress, помилки, diagnostics і technical logs
  англійською (`f3a3333`, `d54e1e2`); сторонні помилки можуть бути мовою ОС.
  Мова інтерфейсу не змінює мову transcript; не перекладати голос автоматично.
- [x] Налаштовувані профілі: language + shared modifiers/A–Z key + delivery
  (clipboard або paste). Без прив'язки U/E/L до фіксованих мов; за потреби
  кілька профілів. English language names та зрозумілі обмеження backend.
- [x] Міграція поточних U/E/L і preferences без зміни звичок існуючих користувачів;
  atomic save, validation, conflict detection та rollback реєстрації shortcuts.
- [x] Простий first-run вибір мови, shortcut, copy/paste та явне завершення
  у Settings — `codex/first-run-settings` (докази нижче).
- [ ] Розширений onboarding E: перевірка мікрофона, permission hints, пояснення
  першого завантаження моделі та тестове диктування.
- [ ] Зіставлення мови з сумісною моделлю: українську спеціалізовану модель не
  використовувати мовчки для польської; явні помилки для непідтримуваних мов.
- [x] Регресії: міграція, конфлікти, restart/persistence, English diagnostics,
  відсутність transcript у технічних логах; CI Windows/macOS/Linux.
- [x] Windows-приймання: розгорнута GitHub-гілка `codex/language-profiles`
  перевірена користувачем 2026-09-22; Language Profiles і paste працюють.
  Це не є hardware acceptance для всього E/F.

Історичний текст вище передував UX-уточненню. Актуальний порядок після D.1:
D.2b Settings redesign → E packaging/installers → F release gate. Не додавати
LLM-переформатування промптів або новий product flow.

### D.2. Сучасний Settings UX — P1

Уточнено 2026-09-25 після перегляду D.2a: Voice to Clipboard лишається
простим застосунком «shortcut → voice → clipboard або guarded paste». Потрібен
лише сучасний і зрозумілий Settings UI, у якому користувач з будь-якою мовою
може налаштувати language profile та щодня користуватися вже наявним flow.

Поточний Tk/ttk panel об'єднує технічні settings, профілі й diagnostics в одну
довгу форму; профіль потребує Add/Update та окремого Apply. Це і є проблема,
яку вирішує D.2b. Диктування, tray, hotkeys, copy/paste, history, worker,
моделі й delivery semantics не є предметом редизайну.

**Цільовий Settings UX**

- Languages — головна сторінка: компактний список «мова / shortcut /
  clipboard або paste», пошук мови та окремий editor profile.
- У profile editor один Save виконує чинні validation, registration та atomic
  persistence; Cancel скасовує чернетку; помилка зберігає введене й показується
  біля відповідного поля. Зберігаються A–Z, унікальність shortcut, profile
  modifiers, модельні обмеження та guarded paste.
- General і Advanced показують тільки існуючі налаштування зрозуміло й без
  технічного шуму. Ефективні значення та успадкування visible; diagnostics
  лишаються за потреби, а не основною частиною flow.
- Existing first-run перетворюється на коротку форму налаштування мови,
  shortcut і delivery. Він не завантажує модель, не перевіряє мікрофон і не
  створює другого setup wizard.
- Єдині spacing, typography, colors, visible focus, keyboard tab order,
  accessible names, light/dark і scaling. UI англійський; мова UI не залежить
  від мови диктування.

**Явні межі**

D.2b не додає Draft, templates, context import, новий workflow, нові типи
delivery, AI/LLM rewriting, cloud, accounts, integrations, auto-send, новий
history subsystem, doctor, download wizard, модельні або audio-функції. Не
переписувати inference/core і не змінювати наявні особисті дані. Новий Settings
UI має бути поверх того самого контрольованого host contract; production UI не
пише `settings.json` напряму. Поточний UI лишається робочим до перевіреної заміни.

**Поставки та порядок**

1. **D.2a — завершене дослідження:** Qt/PySide6, design system і обмежений
   UI/IPC slice перевірені. Частина з Draft-концепцією відхилена власником і не
   переходить у продукт чи acceptance. Технічні докази лишаються в окремій
   research-гілці й не входять у `main`.
2. **D.2b — прийнято й змерджено:** production Settings UI для існуючих profiles,
   General/Advanced і короткого first-run; міграція та регресії. Виконано в окремій гілці від `bc60d3c`; merge `f9c3236`.
3. **E — після D.2b:** packaging spike як частина packaging work, потім
   інсталятори й update/uninstall/autostart. Нових product features для цього
   не додавати.
4. **F:** clean-machine та hardware release acceptance.

**Критерії завершення D.2b**

- [x] У підтвердженому користувачем сценарії додається English або будь-яку підтримувану іншу
  мову, вибирає shortcut і clipboard/paste, зберігає профіль однією дією та
  бачить зрозумілу помилку конфлікту без втрати введення.
- [x] Після restart profiles, modifiers, model overrides, onboarding completion,
  history і наявні settings залишаються сумісними; registration rollback,
  singleton, guarded paste, pause/restart/Quit та idle-without-recording не
  регресують. Тести використовують ізольовані дані.
- [x] Existing dictation flow лишається тим самим: наявні hotkeys та tray дії
  працюють, без додаткових щоденних кроків або обов'язкового нового home screen.
- [ ] Keyboard-only, visible focus, 100/150/200% scaling, light/dark і
  accessible labels перевірені. Непроведені Windows/macOS/screen-reader checks
  позначені явно.
- [x] User acceptance перевіряє налаштування English і щонайменше однієї
  неанглійської мови, edit/remove, conflict, Cancel, Apply/Save, restart і
  звичайне диктування/copy або paste. Зелений CI не замінює цей тест.

Статус: D.2a дала технічний напрям; його функціональне розширення не прийняте.
D.2b прийнято користувачем 2026-09-25 та змерджено (`f9c3236`). Далі E packaging spike.

### E. Просте встановлення — P1

- [ ] Сценарій для користувача — завантаження артефакта з GitHub Releases,
  **без Git, gh, Python, venv і PowerShell як передумов**. Source/pip лишаються developer path.
- [ ] Windows: per-user installer з GUI executable і runtime; macOS ARM64: `.app` у DMG;
  Linux: обрати та перевірити основний пакет для Ubuntu/Pop!_OS (наприклад `.deb`) з
  desktop entry та системними залежностями. Інші дистрибутиви позначати окремо.
- [x] Порівняти збірку PyInstaller/інший bundler коротким spike: native dependencies,
  size, cold start, MLX, PortAudio, worker spawning у frozen executable.
  Обрано PyInstaller onedir; native CI/вимірювання E.1 наведено нижче.
  Альтернативу Qt/Nuitka оцінено документально, не бенчмарковано.
- [ ] Пакет використовує той самий Settings first-run та мовні профілі, що D.2b.
  Не додавати download wizard, doctor, нові audio/model controls або інший
  onboarding flow лише заради інсталятора.
- [ ] Linux/Windows: без NVIDIA — CPU INT8 профіль. NVIDIA перевіряти реальною пробою
  завантаження/inference, не лише `get_cuda_device_count()`.
- [ ] Для `auto` при відсутніх CUDA libraries запропонувати/використати налаштований CPU
  fallback із видимим повідомленням. При явно обраному CUDA — пояснити, що саме відсутнє.
  Не приховувати довільні помилки моделі за fallback.
- [ ] Відділити NVIDIA driver, CUDA runtime/cuBLAS, cuDNN та повний CUDA Toolkit.
  Не вимагати саме Toolkit 12.8 від кожного користувача: він не доведений як обов'язкова
  залежність цього коду. Пінувати перевірену комбінацію CTranslate2/runtime/cuDNN і
  перевірити ліцензії/спосіб доставки бібліотек; за можливості встановлювати їх локально
  для застосунку без ручного PATH/LD_LIBRARY_PATH. Driver має окрему зрозумілу інструкцію.
- [ ] M4: ARM64 збірка, MLX/Metal, перевірка мінімальної macOS; без CUDA/Rosetta.
- [ ] Оновлення та видалення: не дублювати автозапуск, зберігати settings/history,
  видаляти власні launchers; очищення моделей/історії — окремий вибір.
- [ ] Release-артефакти: version, checksums, documented signing/notarization status.
  Сертифікати — зовнішня залежність, не маскувати unsigned build під flawless installer.

Приймання: чиста Windows VM без Git/Python/CUDA; чиста Ubuntu без Git; Mac M4.
На CPU-профілі перше диктування можливе без CUDA. Для NVIDIA — окрема перевірка із
правильною та відсутньою runtime. Відомі помилки інсталяції та дозволів мають
вести до конкретної дії; новий doctor або wizard не є критерієм цієї поставки.

### F. Регресії та release gate — P1, обов'язково перед оголошенням готовності

- [ ] Unit: commands/state machine, suppression policy, layout mapping, paste modifiers,
  spawn flags, deadlines/retries, dependency diagnosis, UTF-8 history.
- [ ] Integration: справжні процеси/IPC, Windows console control event, PID worker,
  фінальний tail, reset/reconnect, завершення слухача, clean install wheel/bundle.
- [ ] Desktop acceptance: справжні вікна й caret, не лише mocked `SendInput`/pynput.
  Автоматизувати в interactive Windows VM; де runner цього не дозволяє — ручний протокол.
- [ ] CI: Linux/Windows/macOS, package imports, installation, збірка артефактів.
  Окремо перевіряти frozen executable, а не тільки `python -m ...`.
- [ ] Hardware: Windows NVIDIA та Mac M4; Linux regression на наявній конфігурації.
- [ ] Протокол sign-in/autostart/uninstall/reinstall; довга сесія, 20+ коротких записів,
  зміна пристрою, відсутність GPU, вихід під час запису/транскрипції.
- [ ] Release notes: що перевірено, що обмежено DE/правами ОС, як повернути попередню версію.

## 4. Розбиття на поставки

1. **PR 1 — структура та baseline:** A, regression fixtures, сумісні CLI wrappers.
2. **PR 2 — Windows worker/stop:** B; реальний Ctrl+C/PID/tail тест.
3. **PR 3 — hotkeys і paste:** C; Windows desktop acceptance до переходу далі.
4. **PR 4 — resident app:** D; tray, конфігурація, автозапуск, shutdown.
5. **PR 5 — installers:** E; frozen build, інсталятори, update/uninstall,
   наявний Settings first-run та інструкції.
6. **PR 6 — release:** F; артефакти, clean-machine прогони, результати acceptance.

Результат кожної поставки: позначені checklist-пункти + коміт/PR + посилання на CI
та протокол ручної перевірки. Не видавати завершення PR 2 за виконання всіх 8 пунктів.

## 5. Межі й рішення, які потрібно підтвердити під час реалізації

- Найперше потрібен доступ до реального Windows-сценарію для відтворення й приймання.
  Linux-тести та mocks не можуть довести відсутність друку літер у Windows.
- Підтримувані версії Windows/macOS і перелік Linux DE зафіксувати в support matrix.
  «Будь-де на комп'ютері» означає звичайну користувацьку графічну сесію, не secure desktop.
- Точний bundler і Wayland paste обрати за результатом spike; macOS Quartz tap
  уже реалізований, але ще потребує фізичного приймання;
  не представляти варіанти як уже перевірені рішення.
- Apple signing/notarization і Windows signing можуть потребувати сертифікатів.
  Підготувати збірку й перевірки незалежно від їх наявності; явно відобразити статус.
- Не обіцяти нуль помилок: ціль — самодіагностика, корисна дія відновлення й відсутність
  ручного пошуку залежностей для підтримуваних конфігурацій.

## 6. Джерела для технічних рішень

- [Windows RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey) — глобальні комбінації та MOD_NOREPEAT.
- [Windows process creation flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags) — CREATE_NEW_PROCESS_GROUP та взаємодія з console flags.
- [Windows SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) — обмеження UIPI, стан клавіш і значення результату.
- [faster-whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu) — runtime залежності CUDA/cuDNN, не вимога універсального Toolkit 12.8.
- [XDG GlobalShortcuts portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html) — можливість реєстрації shortcuts на підтримуваних desktops.

## English-аудит — 2026-09-21, завершення кроку 1 (код)

- [x] Перекладено решту власних runtime-повідомлень: VAD dependency, history
  validation, worker connection timeout, model/transcription retry/error.
- [x] AST-аудит усіх Python-модулів src: єдиний український executable string —
  навмисна ASR vocabulary підказка для української моделі; її не змінено.
  Коментарі/docstrings і користувацький transcript не є текстом інтерфейсу.
- [x] 74 regression tests: OK, 4 platform skips. CLI help перевірено раніше.
- [x] Користувач дозволив merge текстових змін без окремого ручного Windows-приймання.
- CI `35589166283` ще виконувався під час підготовки merge; локальний suite успішний.

Власні повідомлення тепер англійською; сторонні бібліотеки та ОС можуть повертати
помилки мовою системи. Профілі, мовна маршрутизація та first-run UI — наступні
кроки 2–3; D.1 загалом ще відкритий. README/installation оновлено: власні повідомлення англійською.

## Мовні профілі — поставка 2026-09-21

Гілка `codex/language-profiles`; уточнення користувача: тільки English preset
для нової інсталяції, усі інші мови — виключно явний вибір.

- [x] English/E clipboard для чистої інсталяції; CLI default language також en.
- [x] Version 2 preferences; наявні settings/history мігрують U/E/L, видалені
  профілі після збереження не повертаються. Моделі/історія не видаляються.
- [x] Settings: Add/Update/Remove профілю (language, A–Z key, paste, model override),
  спільні modifiers; Apply з validation, registration rollback та atomic persistence.
- [x] Native callbacks і tray/Settings меню будуються лише з обраних профілів.
  macOS physical key mapping розширено до A–Z.
- [x] Вибрана модель/мова явно передаються recorder; стандарт — multilingual turbo,
  без української спеціалізованої моделі. Non-English + .en відхиляється.
- [x] Settings відкривається на першому запуску; README/installation оновлено.
- [x] 80 local regression tests: OK (4 platform skips).
- [x] Local desktop smoke: English-only, застосування Polish, видалення профілю,
  singleton panel і Quit; без мікрофона/завантаження моделі.
- [x] [CI реалізації bc4b718](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35590195313):
  Windows/macOS/Linux × Python 3.11/3.12, усі 6 jobs успішні.
- [ ] Реальне Polish/English диктування та приймання профілів користувачем.
- [x] Незалежні modifiers для кожного профілю — реалізація в `codex/profile-modifiers`;
  ручне приймання та merge окремо нижче.
- [ ] Повний first-run wizard з mic/download progress, перевірка довільних custom model repositories.

[Test guide](../setup/language-profiles.md). Це реалізація основи кроків 2–3,
а не закриття всього D.1/E.

## Незалежні modifiers — поставка 2026-09-22

- [x] Реалізовано у `codex/profile-modifiers` від `main` (`c27e602`): optional
  profile modifiers, успадкування default для старих settings, редактор Settings,
  Windows/macOS/X11 native registrations та збереження чинного rollback.
- [x] Автоматично перевірено локально: 85 regression tests (4 platform skips),
  окремий Quartz matching/repeat test; GUI/native smoke результати у handoff.
- [x] [CI виправлень `50e53c0`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35717812820):
  усі 6 jobs Windows/macOS/Linux × Python 3.11/3.12 успішні.
- [x] Прийнято користувачем: повторний Windows-тест усіх перелічених сценаріїв
  після review fixes, 2026-09-23.
- [x] [CI head `fb8d7f5`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35724815235): успішний.
- [x] Review fixes: schema v3 захищає overrides від старого host при downgrade;
  macOS shutdown і tray updates ставляться в AppKit-чергу, щоб setup thread
  міг завершитися; smoke перевіряє 5 швидких restart/Quit.
  Smoke очікує IPC readiness замість наявності socket path. Локально 88 tests OK
  (4 skips), Tk/native smoke OK; повторний CI успішний. Quit timeout не збільшено.
- [x] Змерджено в `main`: `a91291b`, 2026-09-23.

Межі: літери профілів залишаються унікальними; Wayland — manual bindings.
Onboarding, model download та installers не входять у цю поставку.
Schema v3 відхиляється старими версіями; downgrade потребує сумісної резервної
копії settings. Фізичне macOS/M4-приймання залишається відкритим.

Межі поставки сумісності (тепер завершена, `50af7cd`): зрозумілий вибір моделі у Settings —
валідація відомих model/language обмежень, English пояснення та збереження
custom model overrides. Критерій завершення: відома несумісна пара відхиляється
до запису/завантаження, сумісна зберігається після restart, існуючі профілі й
моделі не замінюються мовчки. Межі: без download wizard, installers або нового
onboarding; невідома custom model позначається як неперевірена.

## Windows feedback follow-up — profiles/settings lifecycle

### Стани цієї поставки

| Частина | Реалізовано | Автоматично перевірено | Прийнято користувачем | Змерджено в `main` |
| --- | --- | --- | --- | --- |
| Мовні профілі та міграція | `bc4b718` | CI 6 jobs, Windows/macOS/Linux | Так, Windows 2026-09-22 | Так, merge цієї поставки в `main` |
| Lifecycle/Windows fixes (Apply, Quit, Tk, paste diagnostics) | `c368776` | CI 6 jobs, Windows/macOS/Linux | Так, Windows 2026-09-22 | Так, merge цієї поставки в `main` |
| Focused review `main...9304704` | 2026-09-22: без доведеного дефекту, код не змінено | 34 релевантні unit-перевірки пройшли локально; один Unix-socket test не запускається в sandbox через `PermissionError`, не є дефектом програми | Не застосовується | Не застосовується |

Реалізація, автоматична перевірка, ручне приймання і merge — окремі стани.
Успішний CI не доводить причину відмови paste на конкретному Windows-комп’ютері.

- [x] All 100 supported languages have full English names; alphabetical dropdown.
- [x] Apply waits for acknowledgment before close, shows persistent saved/error status,
  and blocks repeated saves. Pending edits are not silently discarded on close.
- [x] Missing profiles in an old-host response no longer breaks the panel poll loop;
  compatibility checks explain that the resident app must be restarted after updating.
- [x] Quit acknowledgment closes an idle panel immediately; live profiles refresh
  only on change, preserving selection during periodic status updates.
- [x] GUI smoke covers real Add/Apply/close, malformed host response recovery and Quit;
  desktop smoke now verifies persisted profiles after a full process restart.
- [x] Paste errors distinguish unreachable host from failed target verification;
  Windows CI now tests the remote guard IPC with a real native editor and overlay.
- [x] Користувач повторно розгорнув GitHub-гілку на Windows 2026-09-22:
  Language Profiles, hotkeys і paste працюють. Попередня user-specific відмова
  paste не відтворилась; її не видавати за загальне доведення для іншого hardware.

- [x] Windows 3.11 GUI smoke reproduced a Tk shutdown crash (`Tcl_AsyncDelete`).
  Fixed callback ownership: worker handles integer IDs, UI retains/releases callbacks,
  and shutdown joins the worker. Commit `c368776`.
- [x] [Repeat CI](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35637032624):
  all 6 jobs passed (Windows/macOS/Linux, Python 3.11/3.12), including actual Settings
  interactions and remote-guard native paste on Windows. Local suite: 82 tests, 4 skips.

## Сумісність мови й моделі — поставка 2026-09-23

- [x] Гілка `codex/model-language-compatibility` від актуального `origin/main` `668f297`.
- [x] Editable model lists і English пояснення effective model у Settings.
- [x] Спільна offline validation: English-only aliases, Cantonese token limit;
  Add/Update, Apply у panel/host і запуск recorder блокують відомі несумісні пари.
- [x] Custom IDs/paths — unverified, без вгадування за basename; overrides,
  schema v2/v3, modifiers, unrelated settings зберігаються. Старі несумісні
  налаштування можна відкрити й виправити без автоматичного перезапису.
- [x] Local suite: 94 tests OK, 4 platform skips; реальний Tk smoke перевірив
  rejection, custom warning/persistence, Apply/Close/reload та Quit.
- [x] Local native desktop smoke: tray/controller, Pause/Resume, settings,
  singleton panel, restart/persistence та clean Quit; без mic/model load.
- [x] [CI `00b5d6d`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35828213841):
  усі 6 jobs Windows/macOS/Linux × Python 3.11/3.12 успішні.
- [x] Користувач 2026-09-23 підтвердив усі перелічені ручні сценарії:
  English-only rejection, compatible restart/persistence, custom warning/save,
  incompatible inherited default без зміни saved settings; дозволив merge.
- [x] Сфокусований перегляд validation/read-repair, recorder guard і Settings Apply
  перед merge: блокувальних дефектів не виявлено, функціональний код не змінено.
- [x] Змерджено в `main`: `50af7cd` (реалізація `00b5d6d`).
  Завершена remote-гілка `codex/model-language-compatibility` видалена після push main.
- [ ] Фізичне macOS/M4, реальний voice/GPU та clean-machine release gate залишаються відкритими.

[Інструкція, межі й ручний протокол](../setup/model-compatibility.md).
Без завантаження моделей, inference, wizard або installers. Перевірка мови
не гарантує backend format/availability або існування custom repo; підтверджені
ручні сценарії не є новим доказом для всієї hardware matrix.

### D.1 first-run у наявній Settings — поставка 2026-09-23

Короткий English сценарій вибору мови, shortcut, copy/paste та сумісної моделі
з явним завершенням налаштування. Completion зберігається лише після успішного
Apply; після restart завершений сценарій автоматично не відкривається,
перерваний можна продовжити. Чиста установка має лише English preset до явного
вибору; існуючі profiles/settings/history не змінюються без Apply; помилка Apply
не встановлює completion. Clean/existing/failed Apply/restart сценарії перевірено.
Межі: використовувати наявну Settings, без другого wizard, download progress,
inference doctor, packaging чи installers.
Це була наступна робота після D.1 на момент поставки; актуальний пріоритет
замінено на D.2b Settings redesign у розділі D.2.


- [x] Реалізовано у `codex/first-run-settings` від `origin/main` `e9be15c`:
  English guidance, Finish setup and apply, completion у спільній atomic settings
  transaction, capability check старого host, restart/resume.
- [x] Наявні settings не перезаписуються при старті; clean English preset
  запам'ятовується без completion, щоб перше диктування не запускало legacy migration.
  Schema v2/v3, overrides, modifiers, unrelated fields та history збережено.
- [x] Local suite: 98 tests OK (4 platform skips). Failure checks: validation,
  registration conflict, persistence error; completion і saved bytes не змінюються.
- [x] Real Tk smoke: interrupted/failed setup, resume, Finish/close, completed
  reload, model rejection/custom warning, malformed response recovery та Quit.
- [x] Native Linux desktop smoke: незавершений setup автоматично відкривається
  після restart; завершений — ні; Pause/Resume, singleton, persistence і 5 Quit/restart.
- [x] [CI `8f192b1`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35830338650):
  усі 6 jobs Windows/macOS/Linux × Python 3.11/3.12 успішні.
- [x] Користувач 2026-09-23 підтвердив перелічені ручні сценарії та дозволив
  merge/push і видалення завершеної remote-гілки. Окремої hardware matrix не надано.
- [x] Сфокусований перегляд completion, Apply/rollback, startup та сумісності
  налаштувань перед merge: блокувальних дефектів не виявлено; код не змінювався.
- [x] Змерджено і запушено в `main`: `1a6e23c` (реалізація `8f192b1`).
  Remote-гілку `codex/first-run-settings` видалено після push main.
- [ ] Фізичне macOS/M4, реальний voice/GPU/download та clean-machine release gate.

[Оновлення й ручний тест](../setup/first-run.md). Unsaved edits не відновлюються;
відновлюється сценарій зі збережених профілів. Linux без GTK tray host може
відкрити control panel незалежно від completion. Без voice/GPU/download tests.
Наступна задача на момент завершення D.1 була E packaging spike; цей запис
історичний. Після уточнення D.2 2026-09-25 наступна задача — D.2b Settings
redesign, а packaging/installers переходять після нього. Фізична hardware
matrix та E/F release gates залишаються відкритими.

### Уточнення D.2 після перегляду власником — 2026-09-25

D.2a була технічною пробою, а не прийманням нового продуктового напряму.
Власник залишає Voice to Clipboard простим: shortcut → voice → clipboard або
guarded paste. Наступна реалізація — **D.2b сучасний Settings UX**, після неї
**E packaging/installers**, потім F. Packaging spike входить в E та не блокує
Settings redesign наперед.

Draft, templates, context import, словник, integrations, AI/LLM, нові workflows,
нові delivery modes та нове зберігання вилучені з roadmap і acceptance criteria.
Production UI не замінено цією документаційною зміною.


### D.2b Settings redesign — поставка 2026-09-25

Гілка `codex/settings-redesign` від актуального `origin/main` `bc60d3c`.

- [x] Qt/PySide6 production Settings: Languages, пошук підтримуваної мови,
  окремий profile editor, один Save, Cancel, inline validation/conflicts.
  General/Advanced зберігають тільки власні поля; diagnostics — окрема вкладка.
- [x] Наявний first-run в тому самому editor; completion лише після host Save.
  Немає direct settings writes з UI, нової schema, model/audio чи product features.
- [x] Незмінний host contract і atomic registration/persistence rollback;
  v2/v3, overrides, modifiers, unrelated fields/history та старий host захищені.
- [x] Локальні 99 tests: OK, 4 platform skips. Qt smoke включено у suite;
  він перевіряє failure/retry, malformed replies, Cancel, edit/remove, partial saves,
  completion, restart та keyboard focus на ізольованих даних.
- [x] Native Linux Qt smoke і desktop lifecycle: singleton, pause/resume,
  5 restart/Quit, idle без microphone/model load. Headless scaling 100/150/200%,
  light/dark render, English accessible names; screenshots переглянуто.
- [x] Реалізація `dc1d720`; CI/runtime follow-up `b5aab52`.
  [CI `36128646652`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36128646652):
  усі 6 jobs Windows/macOS/Linux × Python 3.11/3.12 успішні, включно з native
  Qt/lifecycle, Windows remote-guard paste та offscreen scaling. Перший Ubuntu
  CI виявив відсутню libEGL; runtime prerequisites додані до CI й setup docs.
- [ ] Фізичне Windows/macOS, screen-reader, OS theme/display acceptance.
- [x] Користувач 2026-09-25 підтвердив, що перелічені ручні сценарії працюють,
  та дозволив merge/push/delete branch. Це приймання його сценарію, не всієї hardware matrix.
- [x] Сфокусоване review Settings Save/Cancel, host contract, rollback, singleton
  і lifecycle: блокувальних дефектів не знайдено; функціональний код не змінено.
  Merge у `main`: `f9c3236`; main запушено, завершену remote-гілку видалено.

[Оновлення, межі й ручний тест](../setup/settings-redesign.md).
Наступна конкретна задача: **E.1 packaging spike** від актуального main —
перевірити frozen Qt app, worker spawning, native dependencies, size/cold start
на Windows CPU та macOS ARM64; зафіксувати bundler і support matrix до installers.
E.1 розпочато в `codex/packaging-spike` від `27add90`; див. звіт нижче.
E/F hardware, voice/GPU/download, clean-machine gates залишаються відкритими.


### Локальне перенесення після merge — 2026-09-25

Репозиторій і venv перенесено з data folder до
`/home/artem-trybushenko/Projects/voice-to-clipboard`. Особисті data/history/backups
залишено в `~/.local/share/dictate`; моделей/кешів не торкалися. Оновлено тільки
локальні шляхи launcher/venv, GNOME shortcuts і CUDA-параметри збережено.
Після перенесення: 99 tests OK (4 skips), native desktop lifecycle OK,
launcher `dictate --help` працює з іншої папки; history checksum і GNOME bindings
незмінні. Приватна резервна копія — `backups/relocation-2026-09-25` у data folder.

### E.1 packaging spike — поставка 2026-09-25

- [x] Окрема гілка `codex/packaging-spike` від `origin/main` `27add90`.
- [x] PyInstaller onedir spec, explicit frozen child routing, Qt/PortAudio/backend
  probe та реальний worker status/shutdown IPC на ізольованих data/cache.
- [x] Source regression: 104 tests OK, 4 platform skips; схема/settings/history
  та команди source-запуску не змінені.
- [x] Native Windows x64/macOS ARM64 build workflow і збір вимірювань/залежностей.
- [x] Код `70844b7`: [frozen CI 36168009284](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36168009284),
  Windows Server 2025 x64 + macOS 14.8.9 ARM64: Qt/native imports, worker IPC,
  overlay pipe/EOF, native tray/Settings/singleton/persistence і 5 Quit/restart.
- [x] [Regression CI 36168009450](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36168009450):
  6 jobs успішні. Local source suite: 104 tests OK, 4 skips; native Linux lifecycle OK.
- [x] Розміри без моделей: Windows 376 MB, macOS 1.15 GB, Linux 551 MB.
  Повний probe: 3.81/7.62/0.92 s відповідно; Win/Mac містять 2 s overlay wait,
  це не reboot-cold benchmark. PyInstaller onedir залишено для installer work.
- [x] Користувач 2026-09-26 підтвердив усі перелічені ручні пункти на окремій
  Windows 11 AMD64 (build 26200). Локальний frozen probe: worker status/shutdown
  і overlay pipe/EOF OK; Qt 4.185 s, in-process probe 6.568 s.
  Перший наданий JSON — звіт CI; другий — фактичний локальний результат.
- [ ] Фізичний Mac M4, деталізовані voice/GPU/permissions та повна clean-machine matrix.
  Окремого model/device протоколу для optional voice test не надано.
- [x] 2026-09-26: користувач повторно підтвердив сценарії й дозволив merge/push/delete.
  Сфокусоване review frozen routing, Windows streams, launcher guards і перевірок:
  блокувальних дефектів не виявлено; функціональний код не змінено.
  Після `70844b7` були лише docs; тести повторно не запускали.
- [x] Merge `7ba73b2` у `main`, main запушено; `origin/codex/packaging-spike` видалено.

[Межі, вибір bundler, support matrix, точні команди та ручний тест](../setup/packaging-spike.md).
Інсталятори, підпис/нотаризація, update/uninstall/autostart та Linux package
залишаються наступними E-поставками після підтвердження spike.

### Наступна конкретна поставка — E.2 Windows per-user CPU installer

Почати в новій гілці від актуального main; у цьому чаті не розпочато.
Межі: інсталятор на основі перевіреного PyInstaller onedir для Windows x64,
без Git/Python/CUDA як передумов; Start Menu launcher, один керований автозапуск,
upgrade/uninstall без втрати settings/profiles/history. Чинні Settings/first-run
і source-install сумісність зберегти; без нових UI/workflows/download wizard.

Критерії: install → launch → CPU dictation → Quit на чистій Windows VM;
upgrade збережених профілів/історії; enable/disable автозапуск і вхід у систему;
uninstall прибирає власні launchers/autostart, залишає дані; reinstall їх читає.
Додати версію/checksum і чесний signing status та перевірки installer lifecycle.
Вибір installer tooling виконати в E.2. macOS DMG/нотаризація, Linux package,
NVIDIA runtime і повна hardware matrix — окремі наступні поставки.

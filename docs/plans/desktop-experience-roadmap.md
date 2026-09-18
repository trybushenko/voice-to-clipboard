# План: надійне диктування без термінала на Windows, macOS і Linux

Початковий план: 2026-09-14, база `072172a`. Ревізія A/B/C: 2026-09-15,
після `1d545b0`, робоча гілка `codex/windows-hotkeys-paste`.

**Статус: A завершено; B/C прийняті користувачем на Windows 2026-09-17
після focus/overlay виправлень і дозволені до merge в main. Фізична macOS
матриця залишається відкритою. D прийнято користувачем на Windows 2026-09-18 і дозволено до merge в main.
Наступний пріоритет — D.1 (international onboarding), потім E/F.**

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

### D.1. International onboarding — наступна окрема поставка

Заплановано 2026-09-18 за фідбеком користувача та польського тестувальника.
Це новий scope, не незавершена частина прийнятого D. Почати в окремій гілці.

- [ ] English by default для всіх UI, tray, CLI/help, progress, помилок,
  діагностики та технічних логів; переклад README/setup onboarding.
  Мова інтерфейсу не змінює мову transcript; не перекладати голос автоматично.
- [ ] Налаштовувані профілі: language + повна hotkey combination + delivery
  (clipboard або paste). Без прив'язки U/E/L до фіксованих мов; за потреби
  кілька профілів. English language names, пошук та зрозумілі обмеження backend.
- [ ] Міграція поточних U/E/L і preferences без зміни звичок існуючих користувачів;
  atomic save, validation, conflict detection та rollback реєстрації shortcuts.
- [ ] Простий first-run вибір мови, shortcut і copy/paste; перевірка мікрофона,
  permission hints, пояснення першого завантаження моделі та тестове диктування.
- [ ] Зіставлення мови з сумісною моделлю: українську спеціалізовану модель не
  використовувати мовчки для польської; явні помилки для непідтримуваних мов.
- [ ] Регресії: міграція, конфлікти, non-Latin layouts, restart/persistence,
  English diagnostics, відсутність transcript у технічних логах.
- [ ] Приймання: новий польськомовний користувач без знання української проходить
  setup, задає польську мову/власну комбінацію, диктує й отримує clipboard/paste;
  існуючі українські/англійські профілі продовжують працювати.

Після цього — E: installer/runtime, doctor та чисті машини; F: release gate.
Не додавати LLM-переформатування промптів у цю поставку.

### E. Просте встановлення та діагностика — P1

- [ ] Сценарій для користувача — завантаження артефакта з GitHub Releases,
  **без Git, gh, Python, venv і PowerShell як передумов**. Source/pip лишаються developer path.
- [ ] Windows: per-user installer з GUI executable і runtime; macOS ARM64: `.app` у DMG;
  Linux: обрати та перевірити основний пакет для Ubuntu/Pop!_OS (наприклад `.deb`) з
  desktop entry та системними залежностями. Інші дистрибутиви позначати окремо.
- [ ] Порівняти збірку PyInstaller/інший bundler коротким spike: native dependencies,
  size, cold start, MLX, PortAudio, worker spawning у frozen executable.
  Зафіксувати обраний варіант до написання всіх installers.
- [ ] Setup wizard: backend/профіль швидкості, модель і розмір завантаження, download
  progress/cancel/retry, мікрофон і рівень, дозволи, hotkey conflict test, пробна вставка
  в контрольоване поле, автозапуск. Незавершене налаштування можна продовжити.
- [ ] Doctor у GUI та CLI: версії ОС/архітектури, аудіопристрій, права, clipboard,
  shortcuts, writable data paths, місце на диску, модель, driver/runtime та пробна inference.
  Кожна відома помилка містить наступну дію, а технічні деталі доступні окремо.
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
правильною та відсутньою runtime. Offline після кешування моделі, збій мережі,
відсутність диска/мікрофона/дозволу дають конкретні повідомлення, не traceback-only.

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
5. **PR 5 — installers і doctor:** E; first-run wizard, hardware probes, інструкції.
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

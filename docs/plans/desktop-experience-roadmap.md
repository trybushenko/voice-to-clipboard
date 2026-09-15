# План: надійне диктування без термінала на Windows, macOS і Linux

Дата: 2026-09-14. База аналізу: `072172a`.
Статус: **заплановано; виправлення з цього документа ще не реалізовані**.
Документ покриває всі 8 пунктів Windows-фідбеку та спільний сценарій для трьох ОС.
Позначати етапи виконаними лише після наведених перевірок, записуючи коміт і докази.

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

## 2. Що підтверджено кодом, а що потрібно відтворити

| Фідбек | Поточне місце | Висновок / перевірка | Етап |
| --- | --- | --- | --- |
| 1, 6: потрібен запуск без PowerShell | `hotkeys.py:main`, console entry points у `pyproject.toml` | Є ручний слухач; інсталятора, tray і автозапуску немає | D, E |
| 2: L копіює, але не вставляє | `platform_support.py:do_paste`, фінал `dictate.py:main` | `pynput.Controller`, фіксовані 150 мс; немає перевірки цільового вікна та фізичних модифікаторів. Причину конкретного збою відтворити | C |
| 3: друкуються літери хоткеїв | `hotkeys.py:GlobalHotKeys` | Немає нативної реєстрації/поглинання комбінації; перевірити також конфлікт Alt+Shift зі зміною розкладки | C |
| 4, 5: складне встановлення | README, extras у `pyproject.toml`, `speech_backends.py:FasterModel` | Git/Python/runtime налаштовуються вручну; наявність GPU не доводить працездатність CUDA | E |
| 6: Ctrl+C не завершує слухач | `hotkeys.py:listener.join()` | Блокувальне очікування й неповне керування дочірніми процесами; потрібне Windows-відтворення | B, D |
| 7: worker гине, WinError 10054 | `model_service.py:RemoteModel.connect`, `local_ipc.py` | `start_new_session=True` без Windows process-group flags; PermissionError не повторюється. Загибель від Ctrl+C — обґрунтована гіпотеза з фідбеку, підтвердити PID/exit code | B |
| 8: плоска структура | корінь репозиторію, `py-modules` | Код, тести, dev-скрипти й інсталяційний helper перемішані | A |

Зелена попередня CI-матриця не доводить, що вставка, поглинання клавіш чи Ctrl+C
працюють на реальному Windows desktop. Нові acceptance-тести обов'язкові.

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

Цільова структура (нові модулі створювати разом із їх реалізацією, без порожніх заглушок):

```text
src/voice_to_clipboard/
  __init__.py
  __main__.py
  cli.py
  app.py                  # життєвий цикл desktop-застосунку
  config.py
  core/
    recording.py
    speech_gate.py
    transcription.py
    history.py
    session.py
  backends/
    faster_whisper.py
    mlx.py
  worker/
    service.py
    client.py
    protocol.py
  platform/
    windows.py
    macos.py
    linux.py
    paths.py
  ui/
    tray.py
    overlay.py
  setup/
    doctor.py
    autostart.py
tests/
  unit/
  integration/
  desktop/
scripts/                   # benchmark, GUI smoke, developer helpers
packaging/
  windows/
  macos/
  linux/
docs/
  plans/
  setup/
  troubleshooting.md
.github/workflows/
README.md
pyproject.toml
LICENSE
```

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

- [ ] Винести створення дочірніх процесів у спільний platform helper.
- [ ] На Windows використовувати `creationflags=CREATE_NEW_PROCESS_GROUP` для
  persistent worker; на Unix залишити `start_new_session=True`.
  Для GUI/no-console сценарію окремо перевірити `CREATE_NO_WINDOW` або GUI entry point.
  Не поєднувати механічно взаємовиключні/неефективні flags.
- [ ] Перевірити закриття консолі окремо від Ctrl+C: це різні події Windows.
  Звичайний desktop-сценарій узагалі не повинен залежати від консолі.
- [ ] `RemoteModel.connect()`: bounded retry/backoff для тимчасових Windows
  `PermissionError` під час читання/заміни endpoint, а також запуску після stale endpoint.
  Не видаляти endpoint живого worker лише через sharing violation. Після deadline —
  зрозуміла помилка з шляхом і дією, без нескінченного повтору.
- [ ] Атомарне створення/заміна endpoint; окремі bounded retries для Windows file sharing
  при записі та cleanup. Зберегти lock і перевірку локального токена.
- [ ] Перевірити читання фреймів при фрагментації TCP, EOF, reset та повторне підключення.
  Повтор фрагмента не повинен дублювати текст у результаті.
- [ ] Ctrl+C у CLI диктування означає «завершити запис»: закрити мікрофон,
  передати фінальний tail, дочекатися результату та скопіювати його.
- [ ] Ctrl+C у CLI слухача означає «завершити слухач»: замінити безмежний `join()`
  керованим циклом/сигналом зупинки, обмежити очікування та вивести підтвердження.
- [ ] Явно розділити Stop recording, Pause hotkeys і Quit application. Для Quit під час
  запису — завершити/дренувати сесію з видимим станом; дозволити явне скасування,
  якщо обробка зависла. Не вбивати довільні Python-процеси.

Приймання на Windows: PID worker переживає Ctrl+C батьківського диктування;
фінальний tail присутній; наступний запис використовує той самий worker без 10054.
Перевірити холодну модель, теплу модель, зупинку під час завантаження, 20 послідовних
циклів, контрольований crash worker. Окремо тест із реальною CUDA, бо fake-model
тест доводить лише роботу процесів/IPC. `--one-shot` лишається запасним режимом,
а не заміною цього виправлення.

### C. Хоткеї без зайвих літер та справжня автовставка — P0

- [ ] Windows: реалізувати `RegisterHotKey` / `WM_HOTKEY` + `MOD_NOREPEAT`, із
  коректним message loop, реєстрацією/звільненням і відображенням конфліктів.
  Перевірити VK/scancode-поведінку на EN/UK розкладках і лівих/правих модифікаторах.
- [ ] Не вирішувати проблему глобальним `suppress=True`, що блокує весь набір тексту.
  Поглинати лише наші комбінації; звичайні L/U/E та інші shortcuts мають працювати.
- [ ] Виявляти Alt+Shift layout-switch conflict, дозволити зміну комбінацій у налаштуваннях.
  Не змінювати системну розкладку чи її shortcuts без явної дії користувача.
- [ ] Дія визначається при старті сесії: L залишається «copy + paste», навіть якщо
  завершили запис іншою комбінацією; друге натискання — стоп, не новий запис.
- [ ] Windows paste: нативний `SendInput` з правильними 64-bit ctypes структурами,
  кодами клавіш і перевіркою результату замість припущення про успіх `Controller`.
- [ ] Дочекатися фактичного відпускання Alt/Shift/Ctrl з обмеженим timeout;
  не покладатися лише на `sleep(.15)`. Не ламати фізично затиснуті клавіші користувача.
- [ ] Перевірити готовність clipboard, записати цільове вікно на старті, не дати
  overlay/tray забрати фокус. Якщо користувач змінив вікно/поле, не вставляти мовчки
  в випадкове місце: зберегти clipboard і запропонувати повторну вставку.
  Не намагатися довільно відновлювати caret у сторонніх застосунках.
- [ ] Відрізняти «скопійовано», «комбінацію вставки надіслано» і підтверджену GUI-тестом
  вставку: SendInput сам по собі не доводить появу тексту в документі.
- [ ] При помилці показувати коротку дію в tray/overlay; clipboard не втрачати.
- [ ] macOS: нативна реєстрація hotkey або вибірковий event tap після перевірки API;
  Command+V і перевірка Accessibility/Input Monitoring. Linux X11: desktop bindings
  або захоплення комбінацій. Wayland: перевірити GlobalShortcuts portal/backend;
  вставку реалізовувати лише доступним дозволеним механізмом, а не обіцяти підтримку
  через X11-інструменти. Якщо DE не підтримує сценарій — показати це у setup.

Приймання: Notepad, Chrome/Edge і VS Code, EN/UK розкладки, 20 запусків кожної дії;
жодної сторонньої літери, дублювання, автоматичного Enter чи зміни фокусу.
L вставляє на поточний caret у незміненому полі; U/E лише копіюють.
Окремо: довго затиснута комбінація, швидкі натискання, зміна активного вікна,
закриття цільового вікна, звичайні та elevated застосунки.

Межа Windows: UIPI може блокувати введення в застосунок із вищими правами.
Не робити запуск адміністратором типовою вимогою; коректно пояснювати обмеження й
залишати текст у буфері. Secure desktop/екран входу не входять у підтримуваний сценарій.

### D. Desktop-застосунок, tray та автозапуск — P1

- [ ] Єдиний користувацький процес: tray/menu bar, hotkeys, controller сесій, IPC;
  окремий worker для розпізнавання. Мікрофон відкривається лише під час запису.
- [ ] Стани: idle → recording → transcribing → delivered/error → idle;
  disabled та shutting-down обробляються явно. Один активний запис.
- [ ] Пункти tray: почати/завершити, пауза хоткеїв, копіювати останнє, налаштування,
  перевірити систему, відкрити журнал, автозапуск, вийти.
- [ ] Windows: GUI launcher/Start Menu shortcut, користувацький автозапуск при вході
  (обрати один механізм: Startup shortcut або HKCU Run). Не Windows Service у Session 0.
- [ ] macOS: `.app`, menu bar, login item або LaunchAgent користувача.
  Підпис/notarization та стабільний bundle ID врахувати для дозволів після оновлення.
- [ ] Linux: `.desktop` і XDG Autostart; за потреби systemd --user з коректною
  прив'язкою до графічної сесії. Не тримати одночасно два механізми автозапуску.
- [ ] Повторний запуск відкриває стан чинного екземпляра, а не другого слухача.
- [ ] App Exit звільняє hotkeys, microphone, worker, locks і overlay з bounded shutdown.
  Вимкнення автозапуску з GUI має бути перевіреним зворотним шляхом.
- [ ] CLI доступний через user PATH за бажанням, але installer створює всі launcher paths
  самостійно. No-console процеси логують у файл з ротацією, а не у втрачений stderr.

Приймання: установити → ввімкнути автозапуск → sign out/sign in → не відкриваючи
термінал надиктувати U/E/L із браузера та VS Code. Закрити всі термінали — застосунок
працює. Pause/Resume/Exit та повторний запуск не залишають zombie-процесів.

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
- Точний bundler, механізм macOS hotkeys і Wayland paste обрати за результатом spike;
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

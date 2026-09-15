# Windows: повне приймання гілки B/C

Гілка: `codex/windows-hotkeys-paste`. Не мерджимо до завершення цього протоколу.
Перевіряємо всю різницю з main: нативні hotkeys і paste, керування host,
фоновий запуск, worker/console lifecycle та регресії структури A.
Орієнтовно 45–90 хвилин; завантаження моделей може тривати довше.

## 1. Оновлення без змішування старої й нової версій

Заверши поточний запис. У PowerShell перейди в клон репозиторію:

```powershell
cd C:\Users\samba\Projects\voice-to-clipboard
.\.venv\Scripts\voice-hotkeys.exe --quit
.\.venv\Scripts\dictate.exe --unload-model
git status --short
git fetch --prune origin
git switch codex/windows-hotkeys-paste
git pull --ff-only
```

Якщо локальної гілки ще немає, замість `git switch` вище виконай:

```powershell
git switch --track origin/codex/windows-hotkeys-paste
```

Повідомлення «host unavailable» від першого `--quit` нормальне, якщо host не
працював. Якщо стара версія ще не знає `--quit`, заверши її Ctrl+C у її терміналі.
Якщо Git показує твої незакомічені зміни, спершу збережи їх; не роби reset/clean.
Якщо в тебе папка `venv`, заміни `.venv` в усіх командах цього гайду.

```powershell
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys]"
git rev-parse --short HEAD
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -c "import voice_to_clipboard; print(voice_to_clipboard.__file__)"
.\.venv\Scripts\voice-hotkeys.exe --help
.\.venv\Scripts\dictate.exe --help
```

Очікуємо: встановлення успішне; імпорт із цього venv; у help є `--background`,
`--pause`, `--resume`, `--status`, `--stop-recording`, `--quit`.
**Після кожного pull повторно встановлюй пакет:** сам pull не оновлює встановлений CLI.

## 2. Автотести та окрема вставка без моделі

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/check_paste.py
```

Набір містить 59 тестів; на Windows нормально пропускається macOS-only тест.
Жодних ERROR/FAIL. Колишній `Mock.__format__` у workflow не повинен повторитися.
Нативні тести перевіряють UIA event subscription і відсутність консолі у child.

У тестовому вікні натисни **Test native paste**, не перемикай фокус.
Очікуємо PASS: `Перевірка вставки — English 123.` вставлено один раз,
фокус залишився в полі. Цей тест перезаписує clipboard синтетичним текстом,
не вмикає мікрофон і не завантажує модель. Закрий тестове вікно.
Якщо FAIL — збережи точний текст; «SendInput викликано» не замінює видимої вставки.

## 3. Основний фоновий сценарій: термінал можна закрити

```powershell
.\.venv\Scripts\voice-hotkeys.exe --background --hotkey-modifiers alt+shift
.\.venv\Scripts\voice-hotkeys.exe --status
```

Очікуємо JSON зі `state: listening`, `pid` host і `dictation_processes: 0`.
Команда повертає prompt; окрема консоль host не відкривається.
Якщо modifiers конфліктують із перемиканням розкладки Windows, дивись пункт 10.

1. Закрий **усе вікно Windows Terminal/PowerShell хрестиком**.
2. Відкрий Блокнот, постав курсор, натисни Alt+Shift+U.
3. Скажи: «Перевіряю фонове диктування. Останні слова: синій корабель».
4. Повторно натисни Alt+Shift+U, відпусти клавіші, дочекайся результату.
5. Натисни Ctrl+V: має бути повний текст, зокрема фінальні слова.
6. Повтори ще раз: не повинно бути WinError 10054 чи потреби перезапускати host.

Оверлей показує запис/обробку, коротко результат, потім зникає. Мікрофон
вмикається тільки під час запису. Фоновий host сам по собі голос не записує.

Відкрий новий PowerShell, перейди в репозиторій:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --status
.\.venv\Scripts\voice-hotkeys.exe --background
.\.venv\Scripts\voice-hotkeys.exe --status
```

PID до/після повторного `--background` має збігатися. Другий host не створюється.
Параметри нового background-виклику не переналаштовують уже чинний host:
для зміни моделі/modifiers спочатку `--quit`, потім новий запуск.
Це ручний запуск фону на поточний login; installer/tray/автозапуск належать D/E.

## 4. U/E/L у трьох редакторах і двох розкладках

Перевір у Блокноті, Chrome/Edge (звичайне multiline-поле) та VS Code
(новий plain-text файл). Не використовуй поле пароля. Нічого не відправляй.
Для кожного застосунку повтори з EN і UK розкладкою клавіатури.

| Старт → стоп | Що надиктувати | Очікуємо |
| --- | --- | --- |
| U → U | «Це український текст. Останнє слово: кавун» | Поле не змінюється; після Ctrl+V повний український текст |
| E → E | “Please review this function. The final word is pineapple.” | Поле не змінюється; після Ctrl+V англійський текст |
| L → L | «Встав цей текст на місце курсора» | Український текст сам вставився один раз |
| L → U або E | Українська фраза | Вставка зберігається: дію визначає стартовий L |
| U або E → L | Фраза відповідною мовою | Тільки clipboard: стоп через L не змінює стартову дію |

Перед L напиши `ПОЧАТОК  КІНЕЦЬ`, постав курсор між пробілами.
Текст має з'явитися саме там; префікс/суфікс не зникають.
Не повинно додаватися U/E/L/Ю/Л/У, другого примірника тексту чи автоматичного Enter.
Редактор може сам змінювати відступи; відрізняй це від дублювання застосунком.
Статус «Paste shortcut sent» підтверджує надсилання клавіш; успіх — видимий текст.

## 5. Повтори, швидкі натискання та modifiers

1. Утримуй стартову комбінацію 2 секунди. Має початися один запис,
   autorepeat не повинен одразу його зупинити. Відпусти й натисни знову для стопу.
2. Старт і майже миттєвий стоп, поки запускається child або модель.
   Не має бути другого запису чи зависання; порожній transcript тут допустимий.
3. Натисни інший hotkey під час обробки: дочекайся завершення першої сесії;
   не повинно виникнути одночасних recording-процесів або дублювання tail.
4. Повтори з лівими й правими Alt/Shift. Right Alt може бути AltGr — запиши
   конкретну розкладку й поведінку; це не завжди еквівалент звичайного Alt.
5. Для L після стопу тримай Alt/Shift до закінчення обробки й ще понад 2 секунди.
   Очікуємо clipboard-only, без насильного відпускання фізично затиснутих клавіш.
6. Повтори, відпустивши modifiers одразу після стопу: вставка повинна працювати.
7. Після тесту перевір звичайні U/E/L, Shift+літери, Ctrl+C/V та Alt+Tab:
   клавіші не «залипають», звичайний текст не блокується.
8. Виконай 20 коротких циклів у головному редакторі, чергуючи U/E/L.
   Відмічай цикл, дію і результат; кожна сесія завершується один раз.

## 6. Захист від вставки не в те поле

Кожен сценарій — нова L-сесія. Спочатку доведи, що звичайний L у цьому полі працює.

| Дія під час запису/обробки | Правильний результат |
| --- | --- |
| Alt+Tab в інше вікно | Жодної автовставки; transcript у clipboard |
| Перехід в інше поле того самого вікна | Жодної автовставки в нове поле |
| Інше поле → назад у початкове | Автовставка все одно заблокована для цієї сесії |
| Перехід одразу після стартового L | Початкове поле не повинно непомітно замінитися новим |
| Закриття початкового вікна | Не вставляє в наступне активне вікно, host працює далі |
| Повільний/недоступний UI Automation provider | Безпечний clipboard-only, без зависання запису |
| Редактор запущений як адміністратор, host звичайний | Clipboard-only допустимий; UIPI не обходиться |

Спробуй також дуже швидке інше поле → назад. Є події UIA та sticky-блокування,
але ОС/provider можуть затримувати події; не обіцяємо атомарність між останньою
перевіркою і обробкою Ctrl+V цільовим застосунком. Будь-яку вставку в чуже поле
вважай блокером мерджу й надай відтворення.

Клік в інше місце **того самого поля** не є зміною field identity:
вставка може відбутися біля нового caret. Застосунок не відновлює старий курсор.
Після fallback натисни Ctrl+V вручну в потрібному полі та перевір повноту тексту.

## 7. Clipboard і відновлення

1. Зроби U-сесію, перевір Ctrl+V і фінальні слова.
2. Скопіюй інший короткий текст, потім виконай:

```powershell
.\.venv\Scripts\dictate.exe --copy-last
```

3. Ctrl+V має повернути останню диктовку, без нового запису.
4. Для L утримуй modifiers після стопу; якщо зможеш змінити clipboard між
   копіюванням результату й відправленням paste, сторонній вміст не має вставитися.
   Цей timing-тест складно відтворити вручну; основний захист є в автотестах.
   Зміна clipboard **до** завершення транскрипції буде перезаписана результатом — це нормально.
5. Відсутність мовлення не повинна очищувати попередній корисний clipboard.

## 8. Pause / Resume / Stop / Quit

У другому PowerShell з папки репозиторію:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --pause
.\.venv\Scripts\voice-hotkeys.exe --status
.\.venv\Scripts\voice-hotkeys.exe --resume
.\.venv\Scripts\voice-hotkeys.exe --status
```

Очікуємо paused → paused → listening → listening.
На паузі hotkeys звільнені: застосунок не стартує запис і не перехоплює літери.
Повтори pause/resume 10 разів: наступний U запускає рівно один запис.

Почни U, потім `--pause`: **запис триває**, pause вимикає лише hotkeys.
Заверши окремою командою:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --stop-recording
.\.venv\Scripts\voice-hotkeys.exe --resume
```

Повний текст у clipboard; без активного запису `--stop-recording` не запускає новий.
Почни нову U-сесію, продиктуй фінальну фразу й виконай:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
```

Очікуємо acknowledgement `stopping`; далі host чекає tail і закривається.
Поки він дренує запис, не запускай новий. Через кілька секунд `--status` повідомить,
що host недоступний. Модель може залишитися кешованою — це очікувано.
Перехід у PowerShell змінює фокус, тому для L тут правильно отримати clipboard-only.
Повторний `--background` після завершення має працювати.

## 9. B: Ctrl+C, закриття консолі й worker

Спочатку зупини background-host, щоб сценарії не змішувалися:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
.\.venv\Scripts\dictate.exe --unload-model
.\.venv\Scripts\dictate.exe --lang uk --silence 0
```

Скажи фразу з чіткими фінальними словами, натисни Ctrl+C під час мовлення.
Очікуємо завершення запису, очікування моделі, **повний tail у clipboard**, нормальний вихід.
Повтори команду й Ctrl+C: без WinError 10054, без `--one-shot`.

```powershell
.\.venv\Scripts\dictate.exe --model-status
```

Збережи PID worker після першого й другого запису: для тієї самої моделі/backend
він має збігатися. Зміна моделі чи idle unload може законно змінити PID.
Повтори stop одразу після старту cold model; очікування завантаження допустиме.
Порожній надто короткий запис не підтверджує якість tail — повтори з мовленням.

Окремо foreground-host:

```powershell
.\.venv\Scripts\voice-hotkeys.exe
```

Ctrl+C без запису: host виходить, hotkeys звільнені. Запусти знову, почни U,
перейди до його консолі й Ctrl+C: host дренує запис і копіює tail.
Другий Ctrl+C **під час drain** явно скасовує дочірню диктовку; незавершений текст
може бути втрачений — це свідомий cancel, а не звичайний стоп.

Console-close тест:

1. Запусти `voice-hotkeys.exe --background`, закрий launch-консоль хрестиком.
2. Запиши U, стопни, перевір clipboard та PID worker у новому терміналі.
3. Почни ще один U і під час запису закрий відкритий термінал хрестиком.
4. Зупини hotkey з Блокнота; tail має зберегтися, наступний запис працює.
5. PID worker тієї самої моделі не повинен змінитися через закриття термінала.

`CREATE_NO_WINDOW` використовується для worker та фонового host/його дітей.
Foreground-host і CLI, які ти навмисно запустив у консолі, не обіцяють зберігати
активний запис після закриття їхньої консолі хрестиком. Для щоденної роботи — background.

Опційний recovery-тест: після завершеної сесії отримай PID через `--model-status`,
у Task Manager заверши **лише цей worker**, потім запиши ще раз.
Новий worker має піднятися, PID зміниться, транскрипція працює.
Не завершуйте всі python.exe — серед них можуть бути інші програми.
CUDA повтори з `--inference-device cuda`; CPU — з `--inference-device cpu`.
Не перевстановлюй справні CUDA/cuDNN для цього тесту: перевіряємо lifecycle, не setup E.

## 10. Конфлікти розкладки й збереження налаштувань

Якщо Alt+Shift перемикає мову або зайнятий іншим застосунком:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
.\.venv\Scripts\voice-hotkeys.exe --background --hotkey-modifiers ctrl+alt
```

Тепер Ctrl+Alt+U/E/L. Повтори базові U/E/L. Quit, потім background без параметра:
Ctrl+Alt має зберегтися. Повернути default:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
.\.venv\Scripts\voice-hotkeys.exe --background --hotkey-modifiers alt+shift
```

Host не змінює системні мовні налаштування Windows. У background попередження
видно в технічному журналі. Для реального registration conflict резервуй комбінацію
іншою shortcut-програмою: host має дати зрозумілу помилку, не залишити частину hotkeys
зайнятою. Звільни конфлікт і перевір новий запуск. Це необов'язково, якщо такої програми немає.

## 11. Оверлей і діагностика

Перевір: оверлей поверх редактора, не забирає курсор, видимий recording/transcribing,
після результату зникає. Повтори при кількох моніторах/масштабуванні, якщо доступні.
Для порівняння без нього:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
.\.venv\Scripts\voice-hotkeys.exe --background --no-overlay
```

U/E/L працюють так само, тільки без індикатора. Поверни звичайний background після Quit.

```powershell
Get-Content "$env:LOCALAPPDATA\VoiceToClipboard\logs\hotkeys.log" -Tail 80
```

Цей журнал містить host-події, без transcript/audio; перезаписується при новому
фоновому запуску. Вивід dictation children у background не записується.
Якщо child падає, журнал містить код виходу; для повного traceback зупини host
і повтори у foreground. Не публікуй приватні транскрипти з foreground-виводу.
Історія диктування — окремий наявний механізм, вона не вимикається фоновим режимом.

## 12. Приймання та відкат

Блокери: пропадає tail; WinError 10054 після штатного стопу; зайві літери;
дублікати; L не вставляє в звичайний доступний Блокнот; вставка в чуже поле;
background помирає від закриття launch-консолі; зависання чи автотести ERROR/FAIL.
Очікувані fallback: змінений/закритий/недоступний target, UIPI, утримані modifiers,
змінений clipboard. Підтвердження на Windows не замінює фізичне macOS-приймання.

Надішли цей протокол (можна коротко PASS/FAIL/SKIP із причиною):

```text
Commit:
Windows version / Python / CPU or CUDA / GPU:
Keyboard layouts / modifiers:
Автотести / standalone paste:
Background / close terminal idle / close terminal recording / same PID:
Notepad EN+UK: U / E / L:
Browser EN+UK: U / E / L:
VS Code EN+UK: U / E / L:
Mixed start-stop / rapid / repeat / left-right modifiers:
20 cycles:
Other window / other field / return / immediate switch / closed target:
Held modifiers / clipboard / elevated editor:
Pause-resume x10 / pause recording / stop / quit / restart:
Ctrl+C tail / cold-warm / worker PID / recovery:
Overlay / no-overlay:
FAIL: точні кроки, очікування, факт, помилка (без приватного тексту).
```

Щоб повернути main: заверши запис, `--quit`, `--unload-model`, потім:

```powershell
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys]"
```

Історію/моделі видаляти не потрібно. Main може ще не підтримувати background/control:
завершуй новий host **до** перевстановлення старої версії.

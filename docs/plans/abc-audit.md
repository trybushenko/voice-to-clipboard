# Ревізія A/B/C — завершення реалізації, 2026-09-15

Гілка `codex/windows-hotkeys-paste`; A та базовий B уже у main.

| Етап | Реалізація | Приймання |
| --- | --- | --- |
| A | Завершено, 69d97a8 | Попередні clean-wheel/CLI/CI перевірки |
| B | Worker/IPC/Ctrl+C + control CLI + console-independent background | Попередній Windows B прийнятий; новий background потребує фізичного console-close тесту |
| C | Native hotkeys, guarded paste, focus events, settings, overlay | Автотести/локальний GUI; Windows/macOS ручний gate відкритий |

## Завершальні зміни

- Worker і overlay на Windows запускаються CREATE_NO_WINDOW. Background host та
  його діти теж без консолі; звичайні foreground children — NEW_PROCESS_GROUP.
- `voice-hotkeys --background` повертає статус/PID; повторний запуск використовує
  чинний host. CLI pause/resume/status/stop/quit з попередньої ревізії збережені.
- Технічний host log перезаписується при запуску; transcript/audio не потрапляють
  у нього. Вивід recording children у фоні вимкнений; для traceback — foreground.
- Початковий guard живе у host всю сесію; приватний IPC session token дозволяє
  child перевірити саме цей guard. Зниклий host/старий token → ручна вставка.
- Windows UIA focus events у MTA; macOS AXObserver; X11 AT-SPI focused accessible
  і події. Перехід у друге поле й назад не скидає виявлену заборону вставки.
- X11 без GI/Atspi/provider та Wayland мають явний clipboard-only fallback.
  Portal binding не реалізований: це задокументована межа підтримки, не прихований checkbox.

## Перевірки

- 59 локальних тестів: OK, 3 native-only skips на Linux.
- Справжній X11 host: status/pause/resume/stop/quit і cleanup IPC.
- Background host переживає launch-команду; повторний запуск зберігає PID;
  pause/resume/quit працюють, endpoint видаляється.
- GTK/AT-SPI: початкове поле підтверджене; програмний перехід у друге й назад
  залишає guard заблокованим. Без мікрофона/приватного тексту.
- CI реалізації `8a0f34a`: [усі 6 jobs успішні](https://github.com/trybushenko/voice-to-clipboard/actions/runs/34968697926),
  Windows/macOS/Linux × Python 3.11/3.12; Windows перевірив UIA subscription і
  no-console child. Це не замінює фізичне мікрофон/caret acceptance.
- Додатковий GUI smoke виявив успадковані stdout/stderr clipboard-owner процесом;
  виправлено явним DEVNULL, щоб батьківські captured pipes могли закритися.
  Повторний GTK smoke: точний Unicode вставився один раз, фокус збережено, процес завершився.

## Межі та наступна робота

B/C готові до приймання в тестовій гілці, але merge C чекає користувача.
Події accessibility залежать від provider; невизначені поля → clipboard-only.
Атомарну гарантію фокусу під час асинхронного Ctrl+V не заявляємо.
GUI/tray/login startup/installer/doctor залишаються D/E, повна hardware-матриця — F.

[Детальний Windows протокол](../setup/windows-stage-c-test.md) ·
[Головний план з окремими implementation/acceptance checkbox](desktop-experience-roadmap.md).


## Windows-фідбек і виправлення — 2026-09-16

Користувач не прийняв початковий C: standalone paste та L відмовляли з generic
focus error. Реальний GUI-тест відтворив це на Windows 3.11/3.12; попередня CI
перевірка лише створювала UIA-об’єкт і не підтверджувала вставку.

Причина: UIA focus event від неактивної панелі задач (`Shell_TrayWnd`) помилково
робив guard invalid, хоча actual focused element залишався початковим.
Додано перевірку actual focus/sender focus, native keyboard-focus HWND,
точну діагностику помилки та unit regression. Tk provider не розрізняє поля
надійно, тому має явний clipboard-only fallback; GUI smoke використовує Win32 EDIT.
CI тепер перевіряє реальну Unicode-вставку, оверлей та зміну поля з поверненням.
Набір unit/integration виріс до 60 тестів. Повторне фізичне Windows-приймання
залишається відкритим; зелений попередній CI не закривав цей дефект.

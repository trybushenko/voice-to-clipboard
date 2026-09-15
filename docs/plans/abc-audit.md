# Ревізія A/B/C — 2026-09-15

База коду: `1d545b0`; ревізія в гілці `codex/windows-hotkeys-paste`.
Головний checklist: [desktop-experience-roadmap.md](desktop-experience-roadmap.md).

## Висновок

| Етап | Код | Приймання | Що робити далі |
| --- | --- | --- | --- |
| A | Завершено, `69d97a8`, у main | Clean wheel/CLI/worker/tests, legacy launcher перевірені | Нічого доробляти в A; future tray/setup не є боргом A |
| B | Основне завершено, `9f63f2d` + `905c1a6`, у main; Pause/Resume дороблено цією ревізією | Windows-фідбек позитивний; нові control-команди перевірено на X11 | Перевірити control-команди на Windows/macOS; no-console/console-close окремо з D |
| C | Значна частина реалізована, не main | CI і Linux GUI пройшли; немає ручного Windows/macOS протоколу C | Фізична матриця та відкриті cross-platform focus/portal пункти |

## Що було неточно

1. Заголовок досі називав весь проєкт лише запланованим — виправлено.
2. У B process-group fix і no-console вимога були одним checkbox: перше виконано,
   друге ні. Їх розділено; NEW_PROCESS_GROUP не видається за захист від console close.
3. B називався неприйнятим навіть після позитивного Windows-фідбеку користувача.
   Фідбек зафіксовано, але не вигадано відсутні версії ОС, PID або hardware-протокол.
4. C повністю позначався виконаним разом із фізичними EN/UK/caret перевірками,
   яких не було. Реалізацію відокремлено від acceptance; прогалини залишені відкритими.
5. Перший аудит посилався на видалені пласкі модулі. Таблицю оновлено до поточних шляхів.
6. Цільове дерево A містило майбутні tray/setup/packaging: замінено фактичним,
   майбутні модулі явно віднесено до D/E/F.

## Що дороблено в коді

- Додано приватний control IPC для `voice-hotkeys --pause/--resume/--status/
  --stop-recording/--quit` з bounded waits, перевіркою команд і cleanup endpoint.
- Pause звільняє native registrations. Resume створює новий listener; конфлікт
  залишає host на паузі. Generation filter не запускає queued actions старого listener.
- Pause не змінює активну dictation session. Stop recording та Quit/drain/cancel
  мають окремі дії. GUI для них залишається D.
- Windows layout conflict detection враховує сучасні `Language Hotkey` і
  `Layout Hotkey`, навіть якщо старого `Hotkey` немає.
- Додано regression-тести lifecycle, control IPC, quit acknowledgement і registry.

## Докази ревізії

- Локальний набір: 53 тести; native Windows/macOS cases пропускаються на Linux.
- Справжній X11-host, окремі CLI-процеси: status → pause → status → resume →
  stop-recording → quit. Очікувані стани отримано, процес завершився, endpoint видалився.
  Використано ізольовані settings/cache і додаткову комбінацію, без мікрофона.
- Попередній CI C `1d545b0`: шість успішних jobs; це доказ базового C, а не
  ручного підтвердження нових control-команд на Windows/macOS.

## Відкриті речі, які не слід називати виконаними

- No-console запуск, закриття консолі під час recording та повний desktop lifecycle.
  Потрібне Windows-приймання і реалізація з D; GUI launchers/autostart ще відсутні.
- Windows/macOS ручна матриця C: actual text/caret, EN/UK/AltGr, repeated keys, UIPI.
- X11 не має повної identity довільного поля при програмному focus-change всередині
  одного native window; macOS AX snapshot починається вже у recording child.
- Polling має часові прогалини; абсолютної гарантії для миттєвих змін фокусу немає.
- Wayland capability probe не є portal binding; підтримується тільки задокументований
  desktop-shortcut/manual-paste шлях. Автовставка Wayland не реалізована.
- Збереження debug metadata без транскриптів, hardware/support matrix, installers,
  GUI tray/menu, автозапуск і release gate лишаються у відповідних майбутніх пунктах.

Ці обмеження не приховані під зеленими checkbox. Після перевірок оновлювати
конкретний рядок головного плану з результатом і комітом.

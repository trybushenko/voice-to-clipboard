# Етап D — desktop, tray/menu bar та автозапуск

Дата: 2026-09-17. Гілка `codex/desktop-tray-autostart`, база main `ad16169`.
B/C прийняті користувачем і змерджені. 2026-09-18 користувач підтвердив, що D
працює чудово на Windows, та дозволив merge у main. Код D: `3f5c83c`;
документована CI-ревізія: `4f9d03d`.

## Реалізація за вимогами D

| Вимога | Реалізовано | Доказ / межа |
| --- | --- | --- |
| Один controller і tray/menu bar | `desktop_app` запускає native icon loop у main thread, hotkey controller у thread того самого процесу | Desktop lock + hotkey lock; повторний запуск відкриває одну settings-панель |
| Мікрофон тільки під час запису | Idle desktop не створює recording child і не завантажує модель | Smoke перевіряє 0 dictation processes і відсутній worker PID |
| Стани | starting → recording → transcribing → delivered/error; disabled та shutting-down | Приватний atomic status JSON без transcript/audio; delivered повертається в idle через 5 секунд |
| Tray-команди | Ukrainian/English start, stop, pause/resume, copy last, settings/system check, log, login startup, quit/cancel | Використовують той самий private control IPC; меню не створює другий recorder |
| Settings | modifiers, model, inference device, overlay | Не змінюються під час сесії; rollback при registration error; збереження інших preferences |
| Windows launcher | GUI entry point `voice-desktop`, per-user Start Menu `.lnk` на pythonw | Source installation не потребує PATH або admin; Python/runtime bundling — E |
| Windows autostart | Одна власна HKCU Run value | Toggle idempotent; вимкнення видаляє тільки нашу value |
| macOS launcher/menu | `.app` bootstrap у ~/Applications, native Cocoa menu bar, stable bundle ID | Main-thread run; Python має відповідати arm64 для M4; це unsigned developer bundle, не notarized release |
| macOS autostart | Один per-user LaunchAgent з RunAtLoad, без KeepAlive | Вмикання/вимикання файлу; наступний login; вихід з app не перезапускає його |
| Linux launcher/autostart | `.desktop` + XDG Autostart | AppIndicator/Ayatana за наявності; GTK fallback відкриває панель, якщо DE не має tray host |
| Quit/ownership | Припинити hotkeys, дренувати запис до 120 секунд, прибрати дітей/worker/panel/runtime | Desktop володіє Popen worker; terminate/kill лише власних процесів, не всіх Python |
| Cancellation | Під час shutting-down є явна дія cancel | Незавершений transcript може втратитися; звичайний Quit спершу чекає delivery |
| Ізоляція CLI | Desktop має private recording endpoint і model runtime; спільний глобальний recording lock | Desktop stop/cancel не надсилає stop сторонньому CLI recorder |
| Діагностика | Read-only system check, structured child events, log rotation | Без аудіозапису, downloads і GPU inference; повний setup/doctor — E |
| Приватність журналу | 512 KiB × поточний файл + 3 backups | Не логуються transcript/audio; arbitrary child stdout відкидається, stderr приймає лише дозволені event types |
| Reversible setup | Install/update/remove тільки власних launchers та autostart | History/settings/models/venv зберігаються; без підміни системних shortcuts |

## Перевірено під час реалізації

- 74 unit/integration тести на Linux: OK; platform-only checks пропущені за ОС.
- Справжній owned worker: запуск без моделі/мікрофона, повторне використання
  того самого Popen, shutdown і видалення private runtime.
- Linux GUI smoke: native tray loop/controller, pause/resume, settings, invalid
  settings rejection, singleton panel, повторний app launch з тим самим PID, Quit.
- Unit: Linux XDG і macOS plist/bundle install/remove; Windows HKCU value із
  підміною registry, native Windows shortcut test виконується лише на Windows.
- CI розширено real desktop lifecycle smoke на Windows/macOS; macOS без
  Accessibility дозволу має залишати доступну панель з disabled hotkeys.
- [CI для реалізації `3f5c83c`](https://github.com/trybushenko/voice-to-clipboard/actions/runs/35189473637)
  завершився успішно: усі 6 jobs (Windows, macOS, Ubuntu; Python 3.11 і 3.12).
  На Windows пройшли справжня Unicode-вставка та desktop lifecycle smoke;
  на macOS — desktop lifecycle smoke. Це не замінює перевірку login startup
  і диктування на фізичному комп'ютері.

## Приймання та залишок платформної перевірки

Код D реалізований, але sign out/sign in, справжній мікрофон, system tray різних DE,
Windows GPU та фізичний Mac M4 не можна позначити перевіреними лише за CI.
Потрібен [desktop-протокол](../setup/desktop-stage-d-test.md), особливо:

- [x] Windows: користувач прийняв етап D після наданого desktop-протоколу
  (2026-09-18). Окремого покрокового звіту не надано; це user acceptance,
  не твердження про інструментально перевірений кожен edge case.
- [ ] macOS M4: arm64 runtime, `.app`, menu bar, permissions і LaunchAgent on/off.
- [ ] Linux DE: видимість tray або явний panel fallback, XDG startup, старі bindings.
- [ ] Long inference: штатний drain і явний cancel/deadline, без залишених owned processes.

Підпис/нотаризація та включений runtime потребують release packaging E і сертифікатів.
Ця гілка не видає developer `.app`/pip setup за готовий signed installer.

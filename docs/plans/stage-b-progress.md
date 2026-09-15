# Етап B — поточний стан

2026-09-15. Етап A опублікований у коміті `69d97a8`; його CI пройшов на всіх
трьох ОС. Зміни B наразі локальні й не означають завершеного Windows-приймання.

## Реалізовано

- Спільний `platform/processes.py` для worker, hotkey children та overlay.
  Windows: `CREATE_NEW_PROCESS_GROUP`; Unix: `start_new_session=True`.
- Bounded exponential backoff під час підключення, максимум 15 секунд;
  sharing violation не запускає зайвий worker і не видаляє живий endpoint.
  Помилка після deadline містить шлях і дію для користувача.
- Атомарна публікація Windows endpoint через temp + replace, bounded file retries
  для створення/заміни/cleanup. Lock і локальна token authentication збережені.
- Читання фрагментованого handshake та stop-повідомлення; regression-перевірки
  JSON framing, EOF, reset, recovery і відсутності дублювання результатів retry.
- SIGINT у CLI встановлює stop event: запис завершується, останній фрагмент
  передається транскрипції. Подальші Ctrl+C не обривають її очікування.
- Hotkey host використовує керований цикл, обмежений listener join і повідомлення
  про завершення. Quit дренує активних власних дітей; повторний Ctrl+C явно
  скасовує лише їх. Після 15 хвилин host виходить із повідомленням, залишаючи
  незавершену диктовку працювати. Модель не вбивається разом із listener.

## Перевірено тут

- **31 тест пройшов на Linux**.
- Справжній subprocess із fake model: 20 послідовних сесій, SIGINT у клієнті,
  фінальний фрагмент 777 семплів, незмінний PID worker.
- Контрольоване вбивство саме тестового worker: старе з'єднання дає помилку,
  наступний retry запускає новий worker і обробляє фрагмент 123 семпли.
- Справжня CUDA, кешований `large-v3-turbo`: дві сесії з SIGINT у батьківському
  клієнті, декодування синтетичного tail і штатний shutdown. Це не перевірка
  точності реального мовлення й не Windows console-event test.
- Windows process flags і sharing violations перевірені підмінами; TCP transport
  та атомарний replace виконуються реально на Linux.

## Ще потрібно для завершення B

- Нативний Windows console Ctrl+C: broadcast, worker PID, tail у clipboard та
  наступний запис без WinError 10054; cold/warm, stop під час load, 20 циклів.
- Закриття консолі перевірити окремо. Process group захищає від Ctrl+C, але не є
  обіцянкою незалежності від CTRL_CLOSE_EVENT. Перевірити GUI/no-console запуск,
  перш ніж додавати `CREATE_NO_WINDOW`; desktop startup належить наступному етапу.
- Перевірити Windows CUDA та фізичний мікрофон, нативний lifecycle overlay.
- Додати окремий стан Pause hotkeys поряд із Stop recording / Quit application;
  зараз є stop recording та quit/drain/cancel, але немає pause/resume UI.

## Офіційні джерела

Поведінка flags звірена з [Python subprocess](https://docs.python.org/3/library/subprocess.html)
і [Microsoft Process Creation Flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags).
`CREATE_NEW_PROCESS_GROUP` відключає Ctrl+C для нової групи; його не слід
механічно змішувати з `CREATE_NEW_CONSOLE`, який цей прапорець ігнорує.

## Приймання користувачем

Користувач підтвердив успішне проходження Windows-сценаріїв; єдиний збій —
тестова підміна SpeechGate в інтерактивному терміналі. Виправлено в `905c1a6`:
числові поля та явні TTY/non-TTY перевірки. B змерджено в main за погодженням
користувача. Попередній список відкритих пунктів збережений як історія; окремий
Pause/resume UI ще потребує реалізації.

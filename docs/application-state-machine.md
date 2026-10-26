# Диаграмма состояний заявки

```mermaid
stateDiagram-v2
  [*] --> draft
  draft --> submitted: клиент отправил
  needs_info --> submitted: клиент дополнил данные
  submitted --> checking: запущены проверки
  checking --> needs_info: нужны документы/уточнения
  checking --> scoring: проверки пройдены
  checking --> declined: найден стоп-фактор
  scoring --> approved: решение положительное
  scoring --> counteroffer: доступны иные условия
  scoring --> declined: риск/политика не допускают выдачу
  counteroffer --> approved: клиент принял вариант
  counteroffer --> closed: клиент отказался
  approved --> issued: оформление завершено
  draft --> withdrawn
  needs_info --> withdrawn
  submitted --> withdrawn
  checking --> withdrawn
  issued --> [*]
  declined --> [*]
  closed --> [*]
  withdrawn --> [*]
```

Переходы проверяются в `backend/app/conveyor/lifecycle.py`; недопустимый
переход возвращает HTTP 409. Каждое изменение сохраняет автора, причину и
время в журнале статусов. Терминальные состояния `issued`, `declined`,
`closed` и `withdrawn` не допускают продолжения прежнего сценария.

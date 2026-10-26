# Системные тесты

В этом каталоге находятся сквозные проверки полного стенда Docker Compose.
Модульные и компонентные тесты расположены рядом с проверяемыми сервисами:

- `backend/tests/` — рекомендации, кредитная политика, конвейер и инструменты
  агента;
- `external/tests/` — эмулятор внешних источников;
- `tests/` — HTTP-сценарии, охватывающие несколько сервисов.

Системный набор запускается через отдельный сервис `backend-test` и базу
`alfa_system_test`. Поэтому созданные тестами заявки не появляются у
пользователей основного демонстрационного стенда.

После запуска основных сервисов выполните:

```bash
docker compose exec db createdb -U alfa alfa_system_test
docker compose --profile test up --build -d --wait backend-test
docker compose exec \
  -e SYSTEM_API_URL=http://backend-test:8000 \
  -e SYSTEM_FRONTEND_URL=http://frontend:8501 \
  -e SYSTEM_PGADMIN_URL=http://pgadmin:80 \
  -e SYSTEM_OLLAMA_URL=http://host.docker.internal:11434 \
  backend python -m pytest system-tests -q
```

Если база `alfa_system_test` уже существует, повторять `createdb` не нужно.

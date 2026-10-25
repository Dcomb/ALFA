# System tests

This directory contains end-to-end checks for the complete Docker Compose
stack. Unit and component tests stay next to the service they exercise:

- `backend/tests/` - ranking, policy, conveyor and agent helpers;
- `external/tests/` - the external-source simulator;
- `tests/` - HTTP scenarios spanning several services.

Run the system suite after the stack is healthy:

```bash
docker compose exec \
  -e SYSTEM_API_URL=http://backend:8000 \
  -e SYSTEM_FRONTEND_URL=http://frontend:8501 \
  -e SYSTEM_PGADMIN_URL=http://pgadmin:80 \
  -e SYSTEM_OLLAMA_URL=http://host.docker.internal:11434 \
  backend python -m pytest system-tests -q
```

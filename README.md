# ABAP Spec Assist

Веб-помощник написания технических заданий (ТЗ) для SAP/ABAP-разработки.

Ведёт диалог с консультантом, автономно исследует SAP через MCP (read-only),
генерирует `.docx`-ТЗ по корпоративному шаблону и обучается на корпусе прошлых
ТЗ (RAG в Qdrant). Поддерживает два равноправных сценария: **новая разработка**
и **доработка существующего объекта**.

Полное описание архитектуры и дорожной карты — [`docs/tz_assistant_plan.md`](docs/tz_assistant_plan.md).
Инструкции для AI-агентов разработки — [`AGENTS.md`](AGENTS.md).

## Стек

- Python 3.14, FastAPI, Pydantic v2
- LangGraph (оркестрация цепочки агентов; внутри узлов — `openai` SDK напрямую)
- SQLAlchemy Core поверх `aiosqlite` (dev) / `asyncpg` (prod)
- Qdrant (RAG-корпус), MinIO/S3 (`.docx`), RabbitMQ (фоновые задачи)
- React + Vite (`tz_ui`)

## Структура репозитория

```
common/            общий код: config, core-клиенты (llm/mcp/db/qdrant/...), схемы
tz_api/            FastAPI: REST + WebSocket, CRUD ТЗ, генерация
tz_orchestrator/   LangGraph: граф агентов, checkpointing, conditional edges
tz_agents/         роли агентов + промпты (prompts/*.md)
tz_indexer/        воркер индексации архива ТЗ → Qdrant
tz_ui/             React + Vite фронтенд
templates/         docxtpl-шаблоны (new / modification)
migrations/        Alembic (single head для sqlite и postgres)
docs/              план и проектная документация
```

## Быстрый старт (dev)

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp common/config/settings.ini.example common/config/settings.ini   # заполнить значения
.venv/bin/alembic upgrade head
.venv/bin/uvicorn tz_api.main:app --reload --port 8000
```

Инфраструктура для локальной разработки (Qdrant + MinIO + RabbitMQ):

```bash
docker compose up -d
```

## Тесты / линт / типы

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy
```

## Статус

Спринт 1 (фундамент): монорепо, реляционный слой на SQLAlchemy Core (SQLite),
CRUD ТЗ через API, каркас LangGraph с checkpointing, core-клиенты LLM/MCP/Qdrant.

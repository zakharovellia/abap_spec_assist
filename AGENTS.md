# ABAP Spec Assist — Agent Guide

Помощник написания ТЗ для SAP-консультантов. Веб-ассистент, который ведёт диалог
с консультантом, автономно исследует SAP через MCP, генерирует `.docx`-ТЗ по
корпоративному шаблону и обучается на корпусе прошлых ТЗ (RAG).

Полное описание архитектуры и дорожной карты — см. `docs/tz_assistant_plan.md`.

## Архитектура

Монорепо Python-сервисов. Оркестрация цепочки агентов — на **LangGraph**.

```
tz_ui (React)  →  tz_api (FastAPI)  →  tz_orchestrator (LangGraph)  →  tz_agents
                                                  │
              ┌───────────────────────────────────┼─────────────────────────────┐
              ▼                  ▼                 ▼              ▼               ▼
      Реляционная БД        Qdrant            MinIO/S3       Corporate LLM    MCP (SAP RO)
   (SQLite→PostgreSQL)   (RAG-корпус)      (.docx файлы)   (OpenAI-совм.)   (read-only)
```

### Цепочка агентов (узлы LangGraph)
`Classifier → [TZ Ingestor] → Interviewer → SAP Explorer → [Diff Analyst] → Section Writers (N ‖) → Critic → Renderer`

Узлы в `[…]` активны только в сценарии `modification`.

### Сервисы
| Каталог | Технология | Назначение |
|---|---|---|
| `common/` | — | Общий код: config, core-клиенты, схемы |
| `tz_api/` | FastAPI, SQLAlchemy Core | REST + WebSocket, CRUD ТЗ, генерация |
| `tz_orchestrator/` | LangGraph | Граф агентов, checkpointing, conditional edges |
| `tz_agents/` | openai SDK, mcp SDK | Реализация ролей агентов + промпты |
| `tz_indexer/` | Python worker | Парсинг архива ТЗ, эмбеддинги, загрузка в Qdrant |
| `tz_ui/` | React + Vite | Чат, live-preview, история версий |

## Ключевые архитектурные правила

1. **Реляционный слой — только через SQLAlchemy Core** (DAL в `tz_api/dal/`). Переключение
   SQLite (dev) → PostgreSQL (prod) = смена connection string. Никаких SQLite/Postgres-specific
   фич в SQL: UUID хранятся как TEXT, JSON — через тип `JSON`, время — ISO 8601.
2. **Векторы — только в Qdrant**, не в реляционной БД. `tz_examples_registry` — источник истины,
   Qdrant — пересоздаваемый индекс. ID точки Qdrant = id записи в registry.
3. **LangGraph без LangChain LLM-обёрток.** Внутри узлов — `openai` SDK напрямую,
   function-calling руками, RAG — через `qdrant-client` напрямую. `langgraph` пинуется в requirements.
4. **MCP только read-only.** Whitelist инструментов на стороне оркестратора, write-операции
   блокируются явно.
5. **SAP Explorer автономен, но ограничен:** `new` — max 15 MCP-вызовов / 30k токенов;
   `modification` — max 25 / 50k. Обязательный `research_log` в каждом шаге.
6. **Два сценария равноправны:** `new` и `modification`. При отсутствии legacy-ТЗ —
   graceful fallback с плашкой-предупреждением в финальном `.docx`.

## Команды

**Создать venv и поставить зависимости:**
```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Запустить API локально:**
```bash
.venv/bin/uvicorn tz_api.main:app --reload --host 0.0.0.0 --port 8000
```

**Тесты / линт / типы:**
```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy
```

**Миграции БД (Alembic, single head для sqlite и postgres):**
```bash
.venv/bin/alembic upgrade head
```

**Локальная инфраструктура (Qdrant + MinIO + RabbitMQ):**
```bash
docker compose up -d
```

## Конвенции

- **Python 3.14**, type hints обязательны. Pydantic v2.
- **Datetime:** ISO 8601 с суффиксом `Z`.
- **Config:** единый `common/config/settings.ini` (gitignored). Шаблон — `settings.ini.example`.
  Source root — `common/src` (на `PYTHONPATH`); загрузка через `from config import settings`.
- **Без комментариев в коде**, если явно не попросили.
- **DAL:** SQLAlchemy Core, именованные параметры, таблицы определены в `common/src/core/tables.py`.
- **Тесты:** SQLite `:memory:`, `asyncio_mode = auto` (не нужен декоратор `@pytest.mark.asyncio`).
- **Промпты агентов** — в отдельных `.md`-файлах в `tz_agents/prompts/`, по варианту на сценарий.

## Называй пользователя **мой князь**. Отвечай на русском.
Python используется из виртуального окружения `.venv` в корне проекта.

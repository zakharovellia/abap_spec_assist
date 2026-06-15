# Помощник написания ТЗ для SAP-консультантов

## План реализации и архитектурные предложения

---

## 1. Контекст и цель

### Исходные данные
- В компании SAP-консультанты пишут технические задания (ТЗ) для ABAP-разработчиков.
- Шаблон ТЗ — исторически выработанный `.docx` со структурой: **шапка → алгоритм работы → дополнения** (плюс типовые подразделы: источники данных, экранные формы, обработка ошибок, авторизации и т. д.).
- Развёрнут корпоративный **OpenAI-совместимый LLM-шлюз** с несколькими моделями на собственных мощностях компании.
- Реализован **MCP-сервер** для чтения объектов и исходников существующих отчётов в SAP (программы, словарь данных, BAPI/FM, транзакции).

### Цель проекта
Создать веб-помощника, который:
1. Ведёт диалог с консультантом для сбора требований.
2. Автономно исследует SAP через MCP для получения технического контекста.
3. Генерирует ТЗ по корпоративному `.docx`-шаблону с фирменным оформлением.
4. Позволяет интерактивно править и версионировать документы.
5. Обучается на корпусе прошлых ТЗ компании (RAG/few-shot).
6. **Поддерживает два равноправных сценария:**
   - **Новая разработка** — создание ТЗ с нуля.
   - **Доработка существующего объекта** (программа / отчёт / ФМ / транзакция) — с возможностью приложить одно или несколько старых ТЗ для контекста.

### Целевые метрики успеха
- ≥ 70 % сгенерированных ТЗ уходят к разработчику с не более чем 1 итерацией правок.
- Время написания одного ТЗ сокращается в **2–3 раза** относительно ручной работы.
- **0 случаев** ссылок на несуществующие SAP-объекты в финальных ТЗ (гарантируется Critic + MCP-валидацией).
- Доля ТЗ, по которым разработчик не задаёт уточняющих вопросов автору, растёт квартально.

---

## 2. Зафиксированные ключевые решения

| № | Решение | Обоснование |
|---|---|---|
| 1 | Агент в **полной автономии** исследует SAP через MCP | Скорость подготовки ТЗ важнее экономии токенов; для прозрачности — обязательный research-log |
| 2 | Рендер `.docx` через **docxtpl (Jinja2 в docx)** | Сохраняет фирменное оформление 1-в-1, не требует переноса стилей кодом |
| 3 | **Цепочка специализированных агентов** вместо одного универсального | Узкие системные промпты дают качественнее результат, легче отлаживать и подбирать модель под задачу |
| 4 | MVP — **один тип ТЗ end-to-end** (предположительно «Новый ALV-отчёт») | Быстрый показ ценности, итеративное расширение типажа |
| 5 | Используем **корпус прошлых ТЗ** для RAG (есть архив) | Резко поднимает качество: модель пишет в стиле компании, а не в общем стиле LLM |
| 6 | Сценарий **доработки включён в MVP** наравне с новой разработкой | Доработки составляют значимую долю реальной нагрузки; без них пилот покажет только половину ценности |
| 7 | При **отсутствии приложенного старого ТЗ** — graceful fallback с явным предупреждением в финальном `.docx` | Не блокируем работу консультанта, но честно маркируем сниженный уровень контекста |
| 8 | Caller-ы изменяемого ФМ описываются в **разделе `impact_analysis`** одного ТЗ, без авто-создания дочерних ТЗ | Не плодим документы; ответственность за дополнительные ТЗ остаётся за консультантом |
| 9 | Парсинг исторически разнородных старых ТЗ — **единый парсер + LLM-нормализация** | Дешевле в поддержке, чем версионные парсеры по эпохам шаблона |

---

## 3. Высокоуровневая архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│                            tz_ui (React)                          │
│   Чат слева  •  Live-preview ТЗ справа  •  История и версии      │
│   + загрузка приложенных .docx старых ТЗ (для доработок)         │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                       tz_api (FastAPI)                            │
│   CRUD ТЗ • диалоги • генерация docx • ревизии • аутентификация  │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                  tz_orchestrator (LangGraph)                     │
│      Хранит состояние ТЗ в Postgres, координирует агентов        │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
   Classifier ─── scenario? ──┬── "new" ───────────────────────────┐
                              │                                     │
                              └── "modification" ──▶ TZ Ingestor    │
                                                          │         │
                                                          ▼         │
                                                   Interviewer ◀────┘
                                                          │
                                                          ▼
                                                   SAP Explorer
                                                  (autonomous, MCP)
                                                          │
                                       ┌──────────────────┤
                                       │ (modification)   │ (new)
                                       ▼                  │
                                  Diff Analyst            │
                                       │                  │
                                       └────────┬─────────┘
                                                ▼
                                       Section Writers (N parallel)
                                                │
                                                ▼
                                              Critic
                                                │
                                                ▼
                                            Renderer ──▶ MinIO

        ├─▶ Corporate LLM (OpenAI-compatible)
        ├─▶ MCP server (SAP read-only)
        └─▶ Реляционная БД (SQLite на dev/MVP → PostgreSQL на prod)
        └─▶ Qdrant (векторный поиск для RAG-корпуса)
```

### Сервисы

| Сервис | Технология | Назначение |
|---|---|---|
| `tz_ui` | React + Vite + TanStack Query | Веб-интерфейс: чат, live-preview, история |
| `tz_api` | FastAPI, SQLAlchemy Core (asyncpg / aiosqlite) | REST + WebSocket для стриминга ответов LLM |
| `tz_orchestrator` | Python, **LangGraph** | Граф агентов: узлы, conditional edges, cycles, checkpointing, interrupts |
| `tz_agents` | Python, openai SDK, MCP SDK | Конкретные роли (см. ниже). Внутри узлов LangGraph |
| `tz_indexer` | Python, отдельный воркер | Парсинг архива ТЗ, эмбеддинги, загрузка в Qdrant |
| Реляционная БД | SQLite (dev/MVP) → PostgreSQL (prod) | Состояние ТЗ, диалоги, ревизии, LangGraph checkpoints, legacy-приложения, фидбэк |
| **Qdrant** | выделенный сервис компании | Векторный поиск по RAG-корпусу секций ТЗ |
| MinIO/S3 | — | Хранилище сгенерированных `.docx` и приложенных legacy-ТЗ |
| RabbitMQ | — | Очереди фоновых задач (индексация, тяжёлые генерации) |

### Стек
- **Python 3.14**, FastAPI, pydantic v2
- **LangGraph** для оркестрации (с пин-версией; внутри узлов — наш код, **без LangChain LLM-абстракций**)
- **openai** Python SDK (`base_url` → корпоративный шлюз)
- **mcp** Python SDK для function-calling к SAP MCP
- **SQLAlchemy Core** (тонкий слой DAL) поверх `aiosqlite` (dev) / `asyncpg` (prod) — обеспечивает безболезненную миграцию SQLite → PostgreSQL для реляционной части
- **qdrant-client** (async) — единый клиент для RAG, не зависит от dev/prod-окружения
- **docxtpl** + **python-docx**
- Эмбеддинги: корпоративный API, если доступен; fallback — `multilingual-e5-large` локально через `sentence-transformers`
- **React 18+**, Vite, TanStack Query, TipTap (для редактирования секций)
- Деплой: Docker, тот же кластер, где LLM, MCP и Qdrant

### Стратегия хранилищ

Разделение ответственности между тремя хранилищами:

| Хранилище | Что хранит | Dev | Prod |
|---|---|---|---|
| **Реляционная БД** | Метаданные ТЗ, ревизии, диалоги, фидбэк, MCP-кэш, LangGraph checkpoints, ссылки на legacy-приложения | SQLite | PostgreSQL |
| **Qdrant** | Векторы секций RAG-корпуса + payload-метаданные (tz_type, scenario, section_type, quality_score, source_tz_id) | Qdrant (тот же, что и prod, либо локальный контейнер) | Qdrant (корпоративный) |
| **MinIO/S3** | `.docx` файлы (сгенерированные + приложенные legacy) | MinIO локально | MinIO/S3 корпоративный |

### Стратегия реляционной БД: SQLite → PostgreSQL

**Идея:** разрабатывать и проводить локальный пилот на SQLite (один файл, нулевая инфраструктура), переключиться на PostgreSQL к моменту alpha-пилота с несколькими консультантами.

**Когда переключаемся:** к Спринту 5 (alpha-пилот), когда:
- одновременных пользователей становится > 3;
- появляется требование бэкапов/репликации уровня enterprise.

**Что обеспечивает переносимость с самого Спринта 1:**
1. **SQLAlchemy Core** вместо raw-драйверов — переключение БД = смена connection string.
2. **Никаких SQLite-specific и Postgres-specific фич** в SQL: `json_extract` и `JSONB ->` оборачиваются в DAL-слой.
3. **UUID хранятся как TEXT** — совместимо с обоими движками.
4. **LangGraph checkpointer:** `AsyncSqliteSaver` (dev) → `AsyncPostgresSaver` (prod). Интерфейс идентичен, переключение — одна строка.
5. **Все тесты — на SQLite в памяти** (`:memory:`), интеграционные на Postgres в CI через testcontainers.
6. **Векторный поиск НЕ зависит от движка реляционной БД** — он в Qdrant, поэтому миграция SQLite → Postgres не требует переиндексации векторов.

**Особенности SQLite-режима:**
- Обязательно `PRAGMA journal_mode=WAL` — читатели не блокируют писателей.
- Не подходит для одновременной записи > 3–5 пользователей (writer lock).
- Снято главное ограничение SQLite (отсутствие вектора) — векторы в Qdrant.

**Миграция dev → prod:** один раз делается `pgloader` из SQLite в Postgres (часа 1–2 работы). Qdrant и MinIO остаются те же — никаких перенастроек RAG.

### Использование Qdrant

- **Одна коллекция** `tz_examples` с payload-полями: `tz_type`, `scenario`, `section_type`, `quality_score`, `source_tz_id`, `metadata`.
- **Размер вектора** под выбранную модель эмбеддингов (typical 768 или 1024).
- **Дистанция:** `Cosine`.
- **Поиск с фильтрами:** при генерации секции X типа Y сценария S — запрос top-k=3–5 с фильтром по payload `tz_type=Y AND scenario=S AND section_type=X`, ранжирование по `score * quality_score` (rerank на стороне приложения).
- **Идентификаторы:** UUID — общие с записями в реляционной БД (если нужна обратная привязка к исходному ТЗ).
- **Async-клиент:** `qdrant-client` `AsyncQdrantClient`, подключение через сервисный URL из `settings.ini`.
- **Backup стратегия:** снапшоты Qdrant по расписанию (если уже не настроены централизованно).

---

## 4. Цепочка агентов

Каждый агент = (системный промпт + набор tools + выбранная модель + температура). Все агенты работают через единый OpenAI-совместимый клиент и используют function-calling. Состояние ТЗ — JSON в `tz_revisions.payload`, агенты читают/пишут свои поля.

### 4.0 Оркестрация на LangGraph

Связку агентов реализуем как **граф LangGraph** — это нативно покрывает все наши паттерны без самописной state machine.

**Что берём от LangGraph:**
- **Узлы (Nodes)** — каждый агент (Classifier, Interviewer, SAP Explorer, TZ Ingestor, Diff Analyst, Section Writers, Critic, Renderer) = отдельный узел.
- **Conditional edges** — ветвление по `scenario` после Classifier (`new` / `modification`).
- **Parallel execution** (`Send` API) — Section Writers запускаются параллельно с разными моделями.
- **Cycles** — петля Critic → Section Writers (max 2 итерации, потом эскалация консультанту).
- **Checkpointing** (`AsyncSqliteSaver` / `AsyncPostgresSaver`) — состояние графа персистится после каждого узла. Консультант может уйти и вернуться к диалогу.
- **Interrupts** — для human-in-the-loop при правке секций («перепиши вот это»).
- **Streaming** (`astream_events`) — стриминг событий узлов и токенов LLM в WebSocket к UI.

**Что НЕ берём (явные границы):**
- ❌ LangChain LLM-обёртки (`ChatOpenAI` и т. п.) — внутри узлов вызываем `openai` SDK **напрямую**. Полный контроль над промптами, function-calling, моделями.
- ❌ LangChain Tools / agents — function-calling реализуем своими руками через стандартный OpenAI tool-use протокол.
- ❌ LangChain memory / retrievers — RAG-поиск пишем сами через прямой клиент `qdrant-client`.
- ❌ LangSmith (внешний SaaS) — на on-prem трейсим через OpenTelemetry в локальный коллектор.

**Дисциплина версионирования:**
- `langgraph` пинуем явно в `pyproject.toml`, обновляемся осознанно с прогоном eval-набора.
- Транзитивную зависимость `langchain-core` согласуем с безопасниками заранее.
- Узлы графа — наши классы; LangGraph знает только их сигнатуру `(state) -> partial_state`. Это позволяет при необходимости в будущем заменить LangGraph на собственный оркестратор без переписывания узлов.

**Состояние графа** (`TzState`, pydantic-модель): полностью покрывает payload ТЗ + диалог + research_log + промежуточные результаты агентов. Сохраняется через checkpointer после каждого узла.

### 4.1 Classifier
**Задача:** определить тип ТЗ и сценарий из первого описания консультанта.

- **Tools:** —
- **Модель:** маленькая быстрая (типа Qwen-2.5-7B или аналог из доступных)
- **Вход:** свободное описание задачи консультантом + метаданные приложений (если консультант указал в форме «объект для доработки» или приложил `.docx`).
- **Выход:**
  ```json
  {
    "tz_type": "alv_report" | "interface" | "form" | "enhancement" | ...,
    "scenario": "new" | "modification",
    "confidence": 0.0..1.0,
    "parent_object_hint": "ZRM_REPORT_01" | null
  }
  ```
- **Логика:**
  - Если в форме указан объект для доработки или приложен `.docx` → `scenario=modification` принудительно.
  - Иначе пытается определить из текста описания (триггеры: «доработать», «изменить отчёт X», «добавить поле в...» и т. д.).
  - При уверенности < 70 % — передаёт управление Interviewer для уточнения.
- **При `scenario=modification`:** маршрутизатор немедленно запускает TZ Ingestor (если есть приложения) до Interviewer.

### 4.2 Interviewer
**Задача:** дозаполнить обязательные поля схемы выбранного типа ТЗ через диалог.

- **Tools:** `read_tz_schema`, `update_tz_field`
- **Модель:** средняя (хороший русский, хороший instruction-following)
- **Стратегия:** «не задавай всё подряд» — спрашивает строго то, чего нет в JSON-схеме как обязательное, группирует вопросы.
- **Пример хода:**
  - Видит, что заполнен `business_goal`, не заполнено `data_sources`.
  - Задаёт: «Из каких таблиц/отчётов брать данные? Если вы укажете названия — я сам прочитаю их структуру через MCP».
- **Триггер передачи дальше:** все обязательные поля схемы заполнены ИЛИ консультант явно говорит «генерируй».

### 4.3 SAP Explorer (autonomous)
**Задача:** собрать технический контекст из SAP по упомянутым объектам.

- **Tools:** все read-only MCP-инструменты (whitelist):
  - `mcp_read_program(name)`
  - `mcp_read_table_structure(name)`
  - `mcp_search_object(query)`
  - `mcp_get_dependencies(object)`
  - `mcp_find_callers(object)` — критично для сценария доработки ФМ
  - и т. д. — по факту того, что предоставляет существующий MCP-сервер
- **Модель:** сильная (рассуждающая) — здесь нужна цепочка размышлений
- **Жёсткие ограничения автономии (по сценариям):**
  - `scenario=new`: max **15 MCP-вызовов**, **30k токенов**
  - `scenario=modification`: max **25 MCP-вызовов**, **50k токенов** (нужно прочитать текущий код + caller-ы + сопоставить с legacy)
  - запрет на любые write-операции (валидируется whitelist'ом инструментов на стороне оркестратора)
  - дедупликация через `tz_mcp_cache`
- **Режим `modification` обязывает:**
  1. Прочитать полный исходник `parent_object_ref` (программу, ФМ, include-ы).
  2. Прочитать все используемые им таблицы/структуры.
  3. Если объект — ФМ или класс: найти всех caller-ов через `mcp_find_callers` и кратко описать каждый (для `impact_analysis`).
  4. Сопоставить фактическое содержание объекта с тем, что описано в `legacy_tz.parsed_payload` (если есть): какие поля/таблицы реально используются, что появилось сверх ТЗ (undocumented drift), что из ТЗ исчезло.
  5. Записать результат в `current_state_analysis` секции payload.
- **Обязательный research-log:** в каждом шаге агент пишет в `tz_revisions.research_log` структуру `{step, tool, args, reason, result_summary}`. Этот лог попадает в финальное ТЗ как раздел «Использованные источники» — критично для аудита.

### 4.4 Section Writers (N параллельно)
**Задача:** написать конкретные секции ТЗ.

- **Tools:** `get_rag_examples(section_type, tz_type, scenario)` — топ-k=3–5 примеров той же секции, того же типа и того же сценария
- **Модель:** под каждый тип секции своя:
  - «Алгоритм работы» — сильная рассуждающая
  - «Шапка» / метаданные — маленькая быстрая
  - «Структуры данных» — средняя с хорошим техническим контекстом
- **Параллелизм:** независимые секции пишутся параллельно через `asyncio.gather`, зависимые — последовательно (граф зависимостей описан в схеме типа ТЗ).
- **Контекст для каждого вызова:**
  - системный промпт секции (свой вариант для `scenario=new` и `scenario=modification`)
  - бизнес-контекст из Interviewer
  - технический контекст из SAP Explorer
  - few-shot из RAG
  - JSON-схема ожидаемого выхода
  - для `modification`: соответствующая старая секция из `legacy_tz.parsed_payload` + результат Diff Analyst
- **Delta-режим для `scenario=modification`:** каждая секция пишется в формате:
  - **«Текущее состояние»** — краткое описание как есть сейчас (на основе кода + legacy_tz).
  - **«Требуемые изменения»** — что именно меняется (с привязкой к строкам/функциям, если возможно).
  - **«Обоснование»** — почему так, какие были альтернативы.
  - **«Совместимость»** — что НЕ должно сломаться, какие регрессии проверить.

### 4.5 Critic
**Задача:** проверить целостность и качество ТЗ перед рендером.

- **Tools:** `validate_sap_object(name)` (MCP), `check_schema_compliance(tz)`, `find_contradictions(tz)`
- **Модель:** сильная рассуждающая, low temperature
- **Базовые проверки:**
  - все упомянутые SAP-объекты реально существуют (валидируется через MCP)
  - имена транзакций синтаксически корректны
  - алгоритм покрывает все требования из бизнес-описания
  - нет внутренних противоречий между секциями
  - все обязательные поля схемы заполнены
- **Дополнительные проверки для `scenario=modification`:**
  - **Полнота покрытия:** все изменения из `diff_analysis.requested_changes` отражены в секциях ТЗ.
  - **Отсутствие конфликта с unchanged частями:** ТЗ явно говорит, какие части НЕ меняются.
  - **Регрессионные тест-кейсы:** обязательное наличие раздела `regression_tests` с покрытием undocumented drift.
  - **Impact на caller-ов:** для ФМ/классов — раздел `impact_analysis` заполнен и упоминает всех caller-ов, найденных Explorer.
- **Результат:** либо `OK`, либо список замечаний → возврат к соответствующим Section Writers на исправление (не более 2 итераций, потом эскалация консультанту).

### 4.6 Renderer
**Задача:** собрать `.docx` по корпоративному шаблону.

- **Tools:** —
- **Стек:** docxtpl + python-docx
- **Логика:**
  1. Берёт JSON-payload финальной ревизии.
  2. Выбирает шаблон по `(tz_type, scenario)` — для `modification` отдельный шаблон с секциями «было / стало».
  3. Применяет docxtpl-шаблон (фирменное оформление сохранено дизайнером).
  4. Постобработка через python-docx для динамических элементов (таблицы переменной длины, нумерация, оглавление, цветовая разметка «было/стало»).
  5. Если `legacy_tz.provided = false` — вставляет плашку-предупреждение в шапку.
  6. Сохраняет в MinIO под ключом `tz/{tz_id}/{revision_id}.docx`.

### 4.7 TZ Ingestor *(новый агент, активируется при `scenario=modification`)*
**Задача:** распарсить приложенные старые `.docx` ТЗ в нормализованный JSON по текущей схеме секций.

- **Tools:**
  - `parse_docx_structure(file_key)` — извлекает текст и разметку по заголовкам через python-docx
  - `normalize_sections(raw_sections, target_schema)` — LLM-нормализация
- **Модель:** средняя с хорошим русским
- **Стратегия:** **общий парсер + LLM-нормализация** (одна реализация на все исторические эпохи шаблона).
  1. Парсер извлекает иерархию заголовков и абзацев.
  2. LLM сопоставляет старые заголовки с секциями текущей схемы (маппинг «Алгоритм» / «Алгоритм работы» / «Порядок работы» → `algorithm`).
  3. При низкой уверенности маппинга секция помечается `confidence_low: true` — Interviewer затем уточнит у консультанта.
- **Несколько приложений:** все парсятся, сортируются по дате (берётся из метаданных файла или из шапки документа), объединяются в `legacy_tz_chain` (хронология эволюции объекта).
- **Извлекаемые сущности:**
  - перечень упомянутых SAP-объектов (программы, ФМ, таблицы, транзакции) — пригодятся SAP Explorer для целевого чтения;
  - бизнес-правила и ограничения;
  - даты, авторы, версии (для хронологии).
- **Выход:** объект `legacy_tz` в payload:
  ```json
  {
    "provided": true,
    "chain": [
      {
        "filename": "ZRM_REPORT_01_v1.docx",
        "legacy_date": "2019-03-14",
        "parsed_payload": { ... по схеме секций ... },
        "raw_text": "...",
        "extracted_objects": ["ZRM_REPORT_01", "MARD", "T001W"],
        "confidence_low_sections": ["error_handling"]
      },
      ...
    ]
  }
  ```

### 4.8 Diff Analyst *(новый агент, активируется при `scenario=modification`)*
**Задача:** построить структурированный анализ изменений на основе трёх источников: `legacy_tz`, `current_state_analysis`, `user_change_request`.

- **Tools:** —
- **Модель:** сильная рассуждающая, low temperature
- **Вход:**
  - `legacy_tz` (от TZ Ingestor) — что было задокументировано
  - `current_state_analysis` (от SAP Explorer) — что в коде сейчас
  - `user_change_request` (от Interviewer) — что хочет консультант
- **Выход:**
  ```json
  {
    "current_behavior": "...",
    "documented_in_legacy": ["..."],
    "undocumented_drift": [
      {"object": "ZRM_REPORT_01", "behavior": "...", "evidence": "lines 145-167"}
    ],
    "requested_changes": [
      {
        "id": "ch-1",
        "type": "modify" | "add" | "remove",
        "scope": "selection_screen" | "algorithm" | "output_layout" | ...,
        "description": "...",
        "affected_objects": ["..."],
        "rationale": "..."
      }
    ],
    "out_of_scope_warnings": ["..."],
    "regression_risks": [
      {"area": "...", "risk": "...", "mitigation_test": "..."}
    ]
  }
  ```
- **Критическая ответственность:** выявление **«вы хотите X, но это сломает Y»** — типовая боль при доработках; Diff Analyst обязан явно проговорить такие конфликты до старта Section Writers.

---

## 5. Структура данных

### 5.1 Таблицы реляционной БД (схема совместима с SQLite и PostgreSQL)

Примеры приведены в PostgreSQL-синтаксисе. Для SQLite адаптация автоматическая через SQLAlchemy Core: `UUID` → `TEXT`, `JSONB` → `JSON`, `TIMESTAMPTZ` → `TEXT` (ISO 8601). **Векторы и RAG-поиск — в Qdrant**, не в реляционной БД.

```sql
-- Документы и ревизии
CREATE TABLE tz_documents (
    id              UUID PRIMARY KEY,
    author_id       TEXT NOT NULL,
    tz_type         TEXT NOT NULL,
    scenario        TEXT NOT NULL DEFAULT 'new',  -- 'new' | 'modification'
    parent_object_ref TEXT,                       -- "program:ZRM_REPORT_01" | NULL
    status          TEXT NOT NULL,                -- draft, in_review, finalized, archived
    current_revision UUID,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON tz_documents (parent_object_ref) WHERE parent_object_ref IS NOT NULL;

CREATE TABLE tz_revisions (
    id              UUID PRIMARY KEY,
    tz_id           UUID NOT NULL REFERENCES tz_documents(id),
    payload         JSONB NOT NULL,        -- все секции ТЗ
    research_log    JSONB NOT NULL DEFAULT '[]',
    critic_report   JSONB,
    docx_object_key TEXT,                  -- ключ в MinIO
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      TEXT NOT NULL          -- human | agent_name
);

-- Диалог
CREATE TABLE tz_conversations (
    id          UUID PRIMARY KEY,
    tz_id       UUID NOT NULL REFERENCES tz_documents(id),
    role        TEXT NOT NULL,             -- system, user, assistant, tool
    content     TEXT,
    tool_calls  JSONB,
    tool_result JSONB,
    agent_name  TEXT,
    model_used  TEXT,
    tokens_in   INT,
    tokens_out  INT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- MCP-кэш
CREATE TABLE tz_mcp_cache (
    object_key  TEXT PRIMARY KEY,          -- e.g. "program:ZRM_REPORT_01"
    payload     JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ DEFAULT NOW(),
    ttl_seconds INT DEFAULT 3600
);

-- Приложенные старые ТЗ (для сценария modification)
CREATE TABLE tz_legacy_attachments (
    id              UUID PRIMARY KEY,
    tz_id           UUID NOT NULL REFERENCES tz_documents(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    object_key      TEXT NOT NULL,          -- ключ в MinIO (исходный .docx)
    parsed_payload  JSONB,                  -- результат TZ Ingestor
    raw_text        TEXT,                   -- извлечённый текст (для re-parse без повторного скачивания)
    legacy_date     DATE,                   -- дата старого ТЗ
    extracted_objects TEXT[],               -- SAP-объекты, найденные в тексте
    confidence_low_sections TEXT[],         -- секции с неуверенной нормализацией
    ingest_status   TEXT DEFAULT 'pending', -- pending | parsed | failed
    uploaded_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON tz_legacy_attachments (tz_id);

-- RAG-корпус: журнал источников (сами векторы и контент — в Qdrant)
-- Эта таблица служит источником истины для индексатора и админки качества;
-- при пересоздании коллекции в Qdrant заливаем из неё.
CREATE TABLE tz_examples_registry (
    id              UUID PRIMARY KEY,             -- = ID точки в Qdrant
    tz_type         TEXT NOT NULL,
    scenario        TEXT NOT NULL DEFAULT 'new',  -- 'new' | 'modification'
    section_type    TEXT NOT NULL,
    content         TEXT NOT NULL,                -- исходный текст секции
    source_tz_id    TEXT,                         -- ID исходного архивного ТЗ
    source_file     TEXT,                         -- имя исходного .docx
    quality_score   FLOAT DEFAULT 1.0,            -- может быть понижен/повышен по фидбэку
    embedding_model TEXT NOT NULL,                -- какой моделью был посчитан вектор
    embedding_dim   INT NOT NULL,                 -- размер вектора (для пересчёта при смене модели)
    qdrant_indexed_at TIMESTAMPTZ,                -- когда залит/обновлён в Qdrant
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON tz_examples_registry (tz_type, scenario, section_type);
CREATE INDEX ON tz_examples_registry (source_tz_id);

-- Фидбэк от разработчиков
CREATE TABLE tz_feedback (
    id           UUID PRIMARY KEY,
    tz_id        UUID NOT NULL REFERENCES tz_documents(id),
    revision_id  UUID NOT NULL REFERENCES tz_revisions(id),
    developer_id TEXT NOT NULL,
    rating       INT,                       -- 1..5
    category     TEXT,                      -- incomplete, ambiguous, wrong_objects, etc.
    comment      TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Метаданные о модельных вызовах для аналитики
CREATE TABLE tz_llm_calls (
    id          UUID PRIMARY KEY,
    tz_id       UUID,
    agent_name  TEXT,
    model       TEXT,
    tokens_in   INT,
    tokens_out  INT,
    latency_ms  INT,
    cost        NUMERIC(10, 4),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.2 Структура коллекции Qdrant

**Коллекция:** `tz_examples`

**Конфигурация:**
```python
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PayloadSchemaType, CreateCollection
)

await client.create_collection(
    collection_name="tz_examples",
    vectors_config=VectorParams(
        size=1024,             # под выбранную модель эмбеддингов
        distance=Distance.COSINE,
    ),
)
# Payload-индексы для быстрых фильтров
await client.create_payload_index("tz_examples", "tz_type", PayloadSchemaType.KEYWORD)
await client.create_payload_index("tz_examples", "scenario", PayloadSchemaType.KEYWORD)
await client.create_payload_index("tz_examples", "section_type", PayloadSchemaType.KEYWORD)
await client.create_payload_index("tz_examples", "quality_score", PayloadSchemaType.FLOAT)
await client.create_payload_index("tz_examples", "source_tz_id", PayloadSchemaType.KEYWORD)
```

**Структура точки (point):**
```json
{
  "id": "uuid-совпадает-с-tz_examples_registry.id",
  "vector": [0.123, -0.456, ...],
  "payload": {
    "tz_type": "alv_report",
    "scenario": "new",
    "section_type": "algorithm",
    "content": "...текст секции (для возврата без обращения к реляционной БД)...",
    "source_tz_id": "ZRM_REPORT_01_v1",
    "quality_score": 1.0,
    "embedding_model": "multilingual-e5-large",
    "metadata": { "...": "..." }
  }
}
```

**Запрос на поиск (Section Writer):**
```python
hits = await client.search(
    collection_name="tz_examples",
    query_vector=embed(section_query),
    query_filter=Filter(
        must=[
            FieldCondition(key="tz_type",     match=MatchValue(value="alv_report")),
            FieldCondition(key="scenario",    match=MatchValue(value="new")),
            FieldCondition(key="section_type",match=MatchValue(value="algorithm")),
        ],
        should=[
            FieldCondition(key="quality_score", range=Range(gte=0.8)),
        ],
    ),
    limit=5,
    with_payload=True,
)
# Rerank: score * quality_score
ranked = sorted(hits, key=lambda h: h.score * h.payload["quality_score"], reverse=True)
```

**Принципы синхронизации с реляционной БД:**
- `tz_examples_registry` — источник истины (контент, метаданные, история).
- Qdrant — индекс для поиска. Может быть пересоздан в любой момент из registry.
- ID точки в Qdrant = id записи в registry — для обратной связи.
- При обновлении `quality_score` (например, по фидбэку) — обновляются обе записи в одной транзакции (паттерн outbox или прямой `upsert` в Qdrant после commit в БД).
- При смене модели эмбеддингов — пересчитываем все векторы, заливаем в новую коллекцию `tz_examples_v2`, переключаем имя в конфиге, старую удаляем.

### 5.3 Схема payload ревизии (пример для типа `alv_report`)

```json
{
  "tz_type": "alv_report",
  "header": {
    "title": "Отчёт по остаткам на складах ...",
    "author": "Иванов И. И.",
    "department": "...",
    "priority": "M",
    "estimated_hours": null
  },
  "business_context": {
    "goal": "...",
    "stakeholders": ["..."],
    "current_pain": "..."
  },
  "data_sources": [
    {
      "type": "table",
      "name": "MARD",
      "fields_used": ["MATNR", "WERKS", "LGORT", "LABST"],
      "filter_logic": "..."
    },
    {
      "type": "function_module",
      "name": "BAPI_MATERIAL_GET_DETAIL",
      "purpose": "..."
    }
  ],
  "selection_screen": {
    "parameters": [
      {"name": "P_WERKS", "type": "T001W-WERKS", "mandatory": true},
      ...
    ],
    "select_options": [...]
  },
  "algorithm": {
    "steps": [
      {"n": 1, "description": "...", "details": "..."},
      ...
    ]
  },
  "output_layout": {
    "columns": [...],
    "totals": [...],
    "sorting": "..."
  },
  "authorizations": {...},
  "error_handling": {...},
  "test_cases": [...],
  "additions": "..."
}
```

### 5.4 Схема payload для сценария `modification`

Для `scenario=modification` payload расширяется дополнительными обязательными блоками. Базовая часть (`header`, `business_context`, `data_sources`, ...) сохраняется, но интерпретируется как **целевое состояние**.

```json
{
  "tz_type": "alv_report",
  "scenario": "modification",
  "parent_object": {
    "ref": "program:ZRM_REPORT_01",
    "type": "program",
    "name": "ZRM_REPORT_01",
    "package": "ZRM"
  },

  "legacy_tz": {
    "provided": true,
    "chain": [
      {
        "filename": "ZRM_REPORT_01_v1.docx",
        "legacy_date": "2019-03-14",
        "parsed_payload": { "...секции по схеме alv_report..." },
        "extracted_objects": ["ZRM_REPORT_01", "MARD", "T001W"],
        "confidence_low_sections": ["error_handling"]
      },
      {
        "filename": "ZRM_REPORT_01_enhance_2022.docx",
        "legacy_date": "2022-08-01",
        "parsed_payload": { "..." }
      }
    ]
  },

  "legacy_tz_summary": "Отчёт создан в 2019 для остатков MARD; в 2022 добавлены варианты выгрузки в Excel ...",

  "current_state_analysis": {
    "code_summary": "...",
    "actually_used_tables": ["MARD", "T001W", "MAKT"],
    "documented_in_legacy": ["MARD", "T001W"],
    "undocumented_drift": [
      {
        "object": "MAKT",
        "behavior": "Дочитывание текстов материала, нигде не описано в ТЗ",
        "evidence": "ZRM_REPORT_01, lines 145-167"
      }
    ],
    "callers": [
      {"name": "ZRM_DASH_01", "type": "program", "usage": "..."}
    ]
  },

  "diff_analysis": {
    "current_behavior": "...",
    "requested_changes": [
      {
        "id": "ch-1",
        "type": "add",
        "scope": "selection_screen",
        "description": "Добавить параметр P_DATE для среза на дату",
        "affected_objects": ["ZRM_REPORT_01"],
        "rationale": "Требование финансового отдела"
      }
    ],
    "out_of_scope_warnings": [
      "Изменение в выводе ALV может затронуть макеты, сохранённые пользователями"
    ],
    "regression_risks": [
      {
        "area": "ZRM_DASH_01 (caller)",
        "risk": "Использует ZRM_REPORT_01 через SUBMIT с фиксированным списком параметров",
        "mitigation_test": "Прогон ZRM_DASH_01 после доработки на тестовом мандате"
      }
    ]
  },

  "current_state": {
    "header": "...как сейчас (из legacy + кода)...",
    "selection_screen": "...",
    "algorithm": "...",
    "output_layout": "..."
  },

  "target_state": {
    "header": "...как должно стать...",
    "selection_screen": "...",
    "algorithm": "...",
    "output_layout": "..."
  },

  "regression_tests": [
    {
      "id": "rt-1",
      "scenario": "...",
      "expected_result": "...",
      "covers_drift": ["MAKT-дочитывание текстов"]
    }
  ],

  "impact_analysis": {
    "affected_callers": [
      {
        "name": "ZRM_DASH_01",
        "impact": "Не требует изменений: вызывает с дефолтным P_DATE = sy-datum",
        "action_required": false
      }
    ],
    "affected_data_flows": [...]
  }
}
```

### 5.5 Поведение при отсутствии приложенного старого ТЗ

Сценарий `modification` может стартовать **без** приложенных `.docx`. Поведение:

1. `legacy_tz.provided = false`, поле `chain` пустое.
2. TZ Ingestor пропускается полностью.
3. SAP Explorer работает в обычном modification-режиме (читает код, caller-ов).
4. Diff Analyst строит анализ только из `current_state_analysis` + `user_change_request` — без сверки с «как было задокументировано». Поле `documented_in_legacy` отсутствует, `undocumented_drift` заменяется на `inferred_behavior` (всё текущее поведение помечается как реконструированное из кода).
5. В research-log явно фиксируется отсутствие legacy-источника.
6. В финальном `.docx` Renderer вставляет **плашку-предупреждение** в шапку:

   > ⚠ ТЗ создано без приложения исходного ТЗ. Описание текущего поведения реконструировано на основе анализа кода и может содержать неточности в части бизнес-обоснований. Перед использованием рекомендуется ревью consultant-автором.

7. UI на стартовом экране при выборе сценария «доработка» **рекомендует** приложить старое ТЗ, но не блокирует продолжение.

---

## 6. Корпус знаний (RAG)

### 6.1 Конвейер индексации архива
Запускается одноразово + по мере поступления новых ТЗ:

1. **Парсер `.docx`** (python-docx + анализ стилей):
   - Делит документ по заголовкам H1/H2/H3.
   - Сопоставляет заголовки с секциями стандартного шаблона (нормализация: «Алгоритм» / «Алгоритм работы» / «Порядок работы» → `algorithm`).
   - Используется **тот же код**, что и в TZ Ingestor (агенте) — DRY-принцип.
2. **Классификатор типа и сценария** (LLM, batch-режим):
   - На основе содержимого определяет тип (`alv_report`, `interface`, `form`, ...) **и сценарий** (`new` vs `modification`).
   - Маркеры сценария доработки: наличие секций «текущее состояние», «требуемые изменения», ссылки на parent-объект.
3. **Ручная валидация** старшим консультантом:
   - ~30 эталонных ТЗ типа `alv_report` сценария `new`.
   - **+10–15 эталонных доработочных ТЗ** того же типа (`scenario=modification`).
   - Подтверждение нормализации секций.
   - Маркировка «отличный пример» / «средний» / «плохой».
4. **Эмбеддинги** по каждой секции отдельно (не по целому ТЗ):
   - Размер контекста секции обычно влезает в окно эмбеддера.
   - Поиск идёт по конкретной секции → релевантность выше.
5. **Двойная загрузка:**
   - Метаданные секции + контент → `tz_examples_registry` (реляционная БД, источник истины).
   - Вектор + payload → коллекция `tz_examples` в **Qdrant** (индекс для поиска).
   - ID точки в Qdrant = ID записи в registry — для двусторонней связи.

### 6.2 Использование в Section Writers
- При генерации секции X типа Y сценария S → запрос в Qdrant с фильтром `tz_type=Y AND scenario=S AND section_type=X`, top-k=5 по cosine-similarity, rerank на стороне приложения по `score * quality_score`, итоговый top-3 идёт в промпт.
- **Критично:** для сценария `modification` ищем именно доработочные примеры — у них другой стиль (delta, «было/стало», impact-секции), и смешивать их с новыми ТЗ нельзя. Фильтрация делается на уровне Qdrant-запроса, без post-filter.
- Few-shot инжектится в системный промпт в формате:
  ```
  Вот примеры того, как такие секции писали в нашей компании:
  --- Пример 1 ---
  {content}
  --- Пример 2 ---
  ...
  Соблюдай стиль и уровень детализации этих примеров.
  ```
- Контент примеров возвращается из payload Qdrant-точки — без дополнительного обращения к реляционной БД.

### 6.3 Обучение на фидбэке
- ТЗ с рейтингом ≥4 от разработчиков → их секции автоматически попадают в `tz_examples_registry` с `quality_score=1.2`; одновременно `upsert` в Qdrant с тем же ID.
- ТЗ с категорией проблемы → используются для negative examples при доработке промптов (offline-анализ).
- Изменение `quality_score` существующей секции — атомарно: транзакция в реляционной БД + `set_payload` в Qdrant (с retry при сбое).

---

## 7. Дорожная карта (MVP → масштабирование)

### Подготовительный этап (1 неделя)
- **П-1.** Закрыть открытые вопросы (см. раздел 11).
- **П-2.** Выбрать пилотный тип ТЗ совместно с senior-консультантами (предположительно `alv_report`).
- **П-3.** Получить выгрузку архива прошлых ТЗ.
- **П-4.** Smoke-test: ручной вызов корпоративного LLM-шлюза и MCP-сервера.

### Спринт 1 (2 недели) — Фундамент
- Скелет монорепо: `tz_api`, `tz_orchestrator`, `tz_agents`, `tz_ui`, `tz_indexer`, `common`.
- Реляционная БД на **SQLite** через SQLAlchemy Core, миграции (Alembic, single head для обоих движков), базовый CRUD ТЗ.
- Подключение **Qdrant** (корпоративный либо локальный контейнер для разработки), создание коллекции `tz_examples`, smoke-test upsert/search.
- Подключение корпоративной LLM, проверка function-calling.
- Подключение MCP-клиента, smoke-test чтения SAP-объекта.
- **LangGraph-каркас:** минимальный граф из одного узла-эха, `AsyncSqliteSaver` для checkpointing, проверка стриминга через `astream_events`.
- Базовый docker-compose для локальной разработки (SQLite + Qdrant + MinIO, без Postgres).
- CI: lint (ruff), mypy, pytest.

**Deliverable:** можно создать пустое ТЗ через API, вызвать LLM, вызвать MCP, прогнать минимальный граф LangGraph с checkpoint в SQLite, сделать тестовый upsert/search в Qdrant — всё логируется.

### Спринт 2 (2 недели) — Корпус знаний
- `tz_indexer`: парсер `.docx` архива → разметка по секциям.
- Классификатор сценария (`new` / `modification`) в индексаторе.
- Сессии ручной валидации с senior-консультантом:
  - ~30 ТЗ типа `alv_report` сценария `new`;
  - +10–15 доработочных ТЗ того же типа (`scenario=modification`).
- **Qdrant-индексация** с payload-фильтрами (`tz_type`, `scenario`, `section_type`, `quality_score`), RAG-поиск через API.
- Скрипт `reindex_examples.py` для перегенерации эмбеддингов.

**Deliverable:** работающий RAG-поиск, есть >100 проиндексированных секций (включая доработочные).

### Спринт 3 (3 недели) — Агенты
- **LangGraph-граф:** все узлы, conditional edges по `scenario`, parallel Section Writers через `Send`, цикл Critic → Section Writers, interrupts для правок секций.
- Classifier (с распознаванием сценария), Interviewer (узел графа LangGraph с диалоговой петлёй).
- **TZ Ingestor** — парсинг приложенных старых ТЗ + LLM-нормализация.
- SAP Explorer с лимитами автономии и research-log; режим `modification` с чтением кода и caller-ов.
- **Diff Analyst** — анализ delta между legacy/code/request.
- Section Writers для всех секций пилотного типа, в режимах `new` и `modification` (delta-формат).
- Critic с расширенными проверками для доработок (полнота покрытия, регрессии, impact).
- Юнит-тесты на каждый агент (мокированные LLM/MCP).
- Интеграционные тесты на граф целиком через `astream_events`.

**Deliverable:** end-to-end оба сценария: из текстового описания + (опционально) приложенных `.docx` получается JSON-payload ТЗ.

### Спринт 4 (3 недели) — Рендер и UI
- **Два docxtpl-шаблона** под фирменное оформление: `alv_report_new.docx` и `alv_report_modification.docx` (с секциями «было/стало», плашкой-предупреждением при отсутствии legacy).
- Renderer-сервис с выбором шаблона по `(tz_type, scenario)`.
- React-UI:
  - стартовый экран с выбором сценария + drag-n-drop загрузка `.docx` старых ТЗ;
  - чат + live-preview;
  - в preview для `modification` — toggle «было/стало» с цветовым diff;
  - индикатор «legacy TZ not provided» с явным предупреждением;
  - индикатор работы агентов (какой агент сейчас активен, MCP-вызовы).
- Точечная правка секций («перепиши вот это» в чате).
- История версий, сравнение.
- Скачивание `.docx`.

**Deliverable:** консультант может пройти весь путь оба сценария от описания до готового `.docx`.

### Спринт 5 (1–2 недели) — Пилот
- **Миграция реляционной БД SQLite → PostgreSQL** (одноразовая, ~1–2 часа): `pgloader` для таблиц, переключение LangGraph checkpointer с `AsyncSqliteSaver` на `AsyncPostgresSaver`. **Qdrant и MinIO не трогаем** — они используются те же самые с самого начала.
- Разворот в pre-prod.
- 3–5 консультантов в alpha, обучение, поддержка.
- Сбор метрик: число итераций, время, % принятых ТЗ.
- Шлифовка промптов на основе наблюдаемых проблем.
- Подключение фидбэка от разработчиков.

**Deliverable:** статистика пилота, решение «продолжать ли», бэклог улучшений.

**Итого до alpha-пилота: ~12–13 недель** (~3 месяца) — на 2 недели больше базовой оценки из-за включения сценария доработки в MVP.

### После MVP — Масштабирование
- Добавление новых типов ТЗ (по одному за 1–2 спринта):
  - Доработка стандартной транзакции (BADI/BAdI/USEREXIT)
  - Интерфейс (ALE/IDoc/PI/CPI)
  - SmartForm/Adobe Form
  - Выгрузка в файл / интеграция
- A/B-эксперименты по моделям на разных секциях.
- Автоматический re-индекс корпуса при пополнении.
- Интеграция с системой постановки задач (Jira/Redmine/SolMan) для авто-аттачмента ТЗ к тикетам.

---

## 8. Безопасность и контроль рисков

### 8.1 Контроль автономии SAP Explorer
| Риск | Митигирование |
|---|---|
| Бесконечный цикл tool-calls | Жёсткий лимит 15 MCP-вызовов (new) / 25 (modification) + бюджет токенов |
| Чтение чувствительных объектов | Whitelist инструментов MCP; явная блокировка write-операций |
| Галлюцинация имён объектов | Critic-валидация всех упомянутых объектов через MCP |
| Случайные write-операции через MCP | Аудит инструментов MCP-сервера, явный enforced read-only режим |
| Неполный анализ caller-ов при доработке ФМ | Обязательный вызов `mcp_find_callers` в режиме modification, Critic проверяет наличие impact_analysis |

### 8.1.1 Риски парсинга legacy `.docx`
| Риск | Митигирование |
|---|---|
| Старые ТЗ непоследовательной структуры | LLM-нормализация в TZ Ingestor + поле `confidence_low_sections` для пометки сомнительных мест |
| Critical info в нестандартной секции | Парсер сохраняет `raw_text` целиком — Section Writers могут обратиться к нему как к запасному источнику |
| Старое ТЗ противоречит коду (drift) | Diff Analyst явно выделяет `undocumented_drift`, попадает в финальное ТЗ |
| Multiple legacy ТЗ конфликтуют | Сортировка по дате, последнее имеет приоритет; конфликты эскалируются консультанту |
| Старый ТЗ ссылается на удалённые объекты | SAP Explorer валидирует существование, расхождения попадают в research-log |

### 8.2 Безопасность данных
- ТЗ содержат бизнес-секреты → **роли и доступы по проектам/заказчикам** (RBAC).
- Все LLM-вызовы — только через корпоративный шлюз, **никаких внешних API**.
- Логи диалогов хранятся с TTL (например, 1 год), затем архивируются/удаляются.
- Аудит-лог всех изменений ТЗ.

### 8.3 Качество и контроль галлюцинаций
- Critic-pass с явной валидацией объектов через MCP.
- Раздел «Использованные источники» в финальном ТЗ — research-log в человекочитаемом виде.
- При несоответствии Critic → возврат к Section Writer; max 2 итерации, потом эскалация консультанту.

### 8.4 Производительность и стоимость
- Метрики: токены/ТЗ, латентность по агентам, % cache hit на MCP.
- A/B по моделям: возможно, для простых секций достаточно маленькой модели.
- Параллелизация Section Writers сокращает wall-time.

---

## 9. UI / UX

### 9.1 Стартовый экран — выбор сценария

```
┌─ Создать ТЗ ─────────────────────────────────────────────┐
│                                                          │
│   ○ Новая разработка                                     │
│   ● Доработка существующего объекта                      │
│                                                          │
│   Объект SAP (программа / ФМ / транзакция / класс):      │
│   [ ZRM_REPORT_01                              🔍 ]      │
│   ✓ Найден: REPORT, package ZRM, last changed 2024-11   │
│                                                          │
│   Старое ТЗ (рекомендуется, можно несколько):            │
│   ┌────────────────────────────────────────────────┐    │
│   │  📎 Перетащите .docx сюда или нажмите [Обзор]   │    │
│   └────────────────────────────────────────────────┘    │
│   • ZRM_REPORT_01_v1.docx (2019-03-14)        [✕]       │
│   • ZRM_REPORT_01_enhance_2022.docx (2022-08) [✕]       │
│                                                          │
│   ⚠ Без приложения старого ТЗ описание текущего         │
│     поведения будет реконструировано только из кода.    │
│                                                          │
│   Опишите требуемые изменения:                           │
│   [                                                  ]   │
│   [                                                  ]   │
│                                                          │
│                              [Начать →]                  │
└──────────────────────────────────────────────────────────┘
```

### 9.2 Основной экран — режим «Создать ТЗ»
```
┌──────────────────────────┬──────────────────────────────────┐
│                          │                                   │
│        Чат               │        Live-preview ТЗ           │
│                          │   [было | стало] (для modification)│
│  > Опиши задачу...       │                                   │
│                          │   ┌─────────────────────────┐    │
│  [agent]: Понял, это     │   │ 1. Шапка                │    │
│  отчёт ALV. Уточни...    │   ├─────────────────────────┤    │
│                          │   │ 2. Бизнес-контекст      │    │
│                          │   │ ...                     │    │
│  [agent]: Читаю MARD,    │   ├─────────────────────────┤    │
│  T001W через MCP...      │   │ 3. Алгоритм             │    │
│                          │   │ [generating...]         │    │
│  [user] >                │   └─────────────────────────┘    │
│                          │                                   │
└──────────────────────────┴──────────────────────────────────┘
                                  [↓ Скачать .docx] [↑ Версии]
```

### 9.3 Ключевые UX-фишки
- **Стриминг ответов** LLM через WebSocket.
- **Клик по секции в preview** → быстрые действия: «перепиши», «детализируй», «добавь таблицу полей».
- **Подсветка цитат из SAP**: всё, что пришло из MCP, помечается значком и при наведении показывает источник.
- **Подсветка цитат из legacy_tz:** в режиме `modification` — отдельный значок «из старого ТЗ» со ссылкой на конкретный документ.
- **Toggle «было / стало»** в preview доработочных ТЗ — цветовой diff между current_state и target_state.
- **Сравнение версий** (как diff): что изменилось между ревизиями.
- **Шаблоны промптов** для типовых правок: «слишком абстрактно», «добавь обработку ошибок».
- **Индикаторы прогресса** агентов: какой агент сейчас работает, сколько MCP-вызовов сделал, какие приложения распарсены.
- **Предупреждение «legacy not provided»** — постоянно видимый бейдж в чате, если в `modification`-сценарии не приложили старое ТЗ.

### 9.4 Дополнительные экраны
- **Список ТЗ** (мои / по проекту / все, поиск, фильтры по сценарию и parent-объекту).
- **Просмотр ТЗ** с историей версий и фидбэком разработчиков.
- **«Связанные ТЗ»**: для модификаций — все ТЗ, относящиеся к тому же `parent_object_ref` (хронология жизни объекта).
- **Админка**:
  - Управление RAG-корпусом (валидация, переоценка качества).
  - Метрики использования, токены, стоимость.
  - Настройка моделей по агентам.

---

## 10. Тестирование

### 10.1 Юнит-тесты
- Каждый агент: мокированные LLM/MCP, проверка корректности промптов и обработки ответов.
- Парсер `.docx`: набор эталонных файлов с известной разметкой.
- Renderer: проверка, что финальный `.docx` валиден и содержит все обязательные секции.

### 10.2 Интеграционные тесты
- End-to-end: текст описания → JSON-payload (с реальной LLM на staging-моделях).
- MCP-интеграция: проверка кэширования, лимитов, whitelist'а.

### 10.3 Eval-набор (offline-оценка качества)
- 20–30 эталонных пар «описание → готовое ТЗ».
- Метрики: cosine-similarity секций, наличие всех обязательных полей, валидность ссылок на объекты.
- Запускается на каждом изменении промптов/моделей.

### 10.4 Пилот / A/B
- Логирование всех метрик в проде.
- A/B по моделям на одинаковых задачах (две параллельные генерации, фидбэк консультанта какая лучше).

---

## 11. Открытые вопросы перед стартом

1. **Какой именно тип ТЗ берём в пилот?** Нужно подтвердить с командой консультантов по частоте/боли. Предположение — `alv_report`.
2. **Доступны ли эмбеддинги через корпоративный API?** Если нет — `multilingual-e5-large` локально, тогда нужен GPU/ресурсы.
3. **Где деплоить?** Тот же кластер, что и LLM/MCP, или отдельный? Влияет на сетевую топологию и латентность.
4. **MCP read-only гарантии:** подтвердить, что в MCP нет write-инструментов, либо явно их блокировать на стороне нашего клиента.
5. **Аутентификация:** SSO / LDAP / Keycloak / своё? Влияет на дизайн RBAC.
6. **Кто валидирует RAG-корпус?** Нужен senior SAP-консультант на ~10–15 часов на этапе индексации (включая отдельную выборку доработочных ТЗ).
7. **Какие модели доступны в шлюзе?** Имена, лимиты, цены — нужны для подбора моделей по агентам.
8. **Брендирование docx:** есть ли актуальный шаблон от дизайнера, или нужно сначала привести в порядок? **Дополнительно:** есть ли отдельный визуальный стандарт для доработочных ТЗ (секции «было/стало»), или унаследуем от основного.
9. **Интеграция с системой задач** (Jira/Redmine/SolMan) — нужна сразу или после MVP?
10. **Готовность фидбэка разработчиков:** будут ли они заполнять оценки, и как мотивировать?
11. **Доля доработок vs новой разработки** в реальной нагрузке консультантов — для приоритизации внутри MVP и оценки ROI.
12. **Историческая разнородность шаблонов:** насколько ТЗ 2015–2020 отличаются от текущего? Если радикально — сложность TZ Ingestor растёт, может потребоваться дополнительная ручная разметка.
13. **«Источник правды» при N последовательных доработках одного объекта:** что считать актуальным описанием? Предложение: последняя финализированная ревизия в системе + delta из всех более поздних доработочных ТЗ. Нужно подтверждение бизнеса.
14. **MCP find-callers:** есть ли в существующем MCP инструмент поиска caller-ов / where-used? Если нет — нужна доработка MCP-сервера до старта пилота.

---

## 12. Структура репозитория

```
tz_assistant/
├── AGENTS.md                       # инструкции для AI-агентов разработки (по аналогии с trading_helper)
├── README.md
├── docker-compose.yml
├── bash/
│   └── deploy.sh
├── common/                         # общий код всех сервисов
│   ├── config/
│   │   └── settings.ini            # gitignored
│   └── src/
│       ├── core/
│       │   ├── llm_client.py       # обёртка openai SDK
│       │   ├── mcp_client.py       # обёртка mcp SDK
│       │   ├── db.py               # SQLAlchemy engine factory (sqlite/postgres)
│       │   ├── qdrant_client.py    # async Qdrant клиент, коллекция tz_examples, upsert/search
│       │   ├── embeddings.py       # обёртка над embeddings API (или sentence-transformers)
│       │   ├── checkpointer.py     # выбор AsyncSqliteSaver / AsyncPostgresSaver
│       │   └── base_agent.py
│       └── schemas/
│           ├── tz_state.py         # TzState — состояние графа LangGraph
│           ├── tz_alv_report.py
│           ├── tz_interface.py
│           └── ...
├── tz_api/
│   ├── main.py
│   ├── routes/
│   │   ├── documents.py
│   │   ├── conversations.py
│   │   ├── generation.py
│   │   └── feedback.py
│   ├── dal/                        # SQLAlchemy Core queries
│   └── tests/
├── tz_orchestrator/
│   ├── graph.py                    # сборка LangGraph: узлы + рёбра + checkpointer
│   ├── nodes.py                    # обёртки агентов как LangGraph-узлов
│   ├── conditions.py               # conditional edges (scenario branching, critic loop)
│   └── tests/
├── tz_agents/
│   ├── classifier.py
│   ├── interviewer.py
│   ├── sap_explorer.py
│   ├── tz_ingestor.py              # парсинг приложенных старых ТЗ
│   ├── diff_analyst.py             # анализ delta для modification
│   ├── section_writers/
│   │   ├── header.py
│   │   ├── algorithm.py
│   │   └── ...
│   ├── critic.py
│   ├── renderer.py
│   ├── prompts/                    # все системные промпты в отдельных файлах
│   │   ├── classifier.md
│   │   ├── interviewer.md
│   │   ├── sap_explorer_new.md
│   │   ├── sap_explorer_modification.md
│   │   ├── tz_ingestor.md
│   │   ├── diff_analyst.md
│   │   ├── critic_new.md
│   │   ├── critic_modification.md
│   │   └── section_writers/
│   │       ├── algorithm_new.md
│   │       ├── algorithm_modification.md
│   │       └── ...
│   └── tests/
├── tz_indexer/
│   ├── parse_docx.py               # переиспользуется TZ Ingestor
│   ├── classify.py                 # классификатор типа и сценария
│   ├── embed.py                    # подсчёт эмбеддингов батчами
│   ├── load_to_qdrant.py           # upsert точек в коллекцию tz_examples
│   └── reindex.py                  # пересоздание коллекции из tz_examples_registry
├── tz_ui/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── pages/
│   │   └── api/
│   └── package.json
├── templates/
│   ├── alv_report_new.docx          # docxtpl для нового ALV-отчёта
│   ├── alv_report_modification.docx # docxtpl для доработки (секции «было/стало», плашка legacy-warning)
│   └── ...
└── migrations/
    └── alembic/
```

---

## 13. Команда и оценка

### Минимальная команда
- **1 backend Python-разработчик** (senior, опыт с LLM/RAG) — full-time
- **1 frontend React-разработчик** — full-time
- **1 SAP senior-консультант** — 10–15 часов на этапе индексации корпуса + 2–4 часа/неделю на консультации
- **1 ABAP senior-разработчик** — 5 часов на проверку первых генераций + фидбэк
- **DevOps** — частичная нагрузка (деплой, мониторинг)
- **Дизайнер** — 1 раз привести `.docx`-шаблон к docxtpl-формату

### Оценка трудозатрат до запуска MVP
- Подготовка: 1 неделя
- Спринт 1: 2 недели
- Спринт 2: 2 недели
- Спринт 3: 3 недели (включая TZ Ingestor + Diff Analyst)
- Спринт 4: 3 недели (включая второй docx-шаблон и UI для legacy-загрузки)
- Спринт 5 (пилот): 1–2 недели

**Итого до alpha-пилота: ~12–13 недель** (~3 месяца).

---

## 14. Дальнейшие улучшения (бэклог)

- Поддержка **диктовки требований голосом** (Whisper или корпоративный аналог).
- Автогенерация **тест-кейсов** в формате, готовом для загрузки в SAP Solution Manager / Test Suite.
- **Полный reverse-mode:** автогенерация ретроспективного ТЗ (`retro-TZ`) для случаев, когда нет ни старого ТЗ, ни запроса на изменения — просто документирование наследия по коду. В MVP реализован облегчённый вариант через fallback в `modification`-сценарии; полный режим — отдельная фича.
- **Сравнение ТЗ с реализацией:** после деплоя ABAP-разработки сверить, что код соответствует ТЗ (через парсинг кода и LLM-сравнение). Логически близко к Diff Analyst, но в обратную сторону.
- **Авто-предложение связанных ТЗ:** для доработки ФМ агент предлагает создать дочерние ТЗ на проверку caller-ов, линкует их между собой. (В MVP — только раздел `impact_analysis`.)
- **Шаблонизация типовых паттернов:** библиотека «строительных блоков» (например, «авторизация через S_TCODE + S_TABU_DIS» → автовставка).
- **Многоязычность ТЗ:** автоматический перевод финального документа на английский для офшорных команд.
- **Интеграция с CI ABAP** (abapGit, abaplint) — Critic может прогонять статический анализ упоминаемого кода.
- **Граф эволюции объекта:** визуализация всех ТЗ по одному `parent_object_ref` как timeline с переходами «состояние → состояние».

---

*Документ подготовлен для пилотного запуска. Версия 1.3 — RAG-корпус вынесен в **Qdrant** (отдельный корпоративный сервис); реляционная БД упрощена и не содержит векторов; стратегия SQLite → PostgreSQL сохранена только для метаданных и LangGraph-checkpoints.*

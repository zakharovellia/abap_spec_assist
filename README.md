# ТЗ-ассистент ABAP

ИИ-помощник для SAP-консультантов: помогает писать и дорабатывать технические
задания (ТЗ) на разработку для ABAP-программистов.

- **Backend** — Python: FastAPI + LangGraph (агент с инструментом `update_spec`,
  состояние сессий в чекпоинтере LangGraph).
- **Frontend** — React (Vite + TypeScript): чат, кнопка 📎 для загрузки
  существующего ТЗ (.docx / .md / .txt — основной сценарий), живое
  Markdown-превью документа ТЗ.
- **LLM** — любой OpenAI-совместимый шлюз (настраивается через `.env`).
- **RAG** — Qdrant с базой примеров реальных ТЗ: перед ответом агент получает
  похожие фрагменты и опирается на них как на образец стиля и оформления.

## Как это работает

Граф LangGraph: `retrieve → assistant → (есть tool-call?) → tools → assistant → END`.

Узел `retrieve` эмбеддит последний запрос пользователя и ищет в Qdrant топ-K
фрагментов реальных ТЗ; они попадают в системный промпт как образцы стиля
(структура разделов, оформление таблиц, терминология — без копирования
содержимого). Если Qdrant или сервис эмбеддингов недоступны, ассистент
продолжает работать без примеров (предупреждение в логе).

Узел `tools` исполняет вызовы инструментов ассистента:

- `update_spec` — замена документа ТЗ в состоянии сессии;
- инструменты **MCP-сервера ADT tools** (чтение объектов SAP: структуры
  таблиц, программы, поиск объектов). Подключаются на старте из
  `MCP_SERVER_URL` (streamable_http, Bearer-токен из `MCP_AUTH_TOKEN`);
  пишущие инструменты (`create_/update_/delete_/activate_/transport_...`)
  отфильтровываются — ассистент читает систему, но не меняет её. Агент
  проверяет реальные таблицы/поля перед тем, как писать их в ТЗ; если
  MCP-сервер недоступен, работает без него и помечает объекты как
  «уточнить в системе».
Агент отвечает в чат, а когда нужно изменить документ — вызывает инструмент
`update_spec` с полным новым текстом ТЗ в Markdown. Текст документа хранится в
состоянии графа (`spec_markdown`) и после каждого хода возвращается фронтенду
для превью. Загруженный .docx конвертируется в Markdown (заголовки, списки,
таблицы) и кладётся в состояние как отправная точка.

## Запуск

### Qdrant (база примеров ТЗ)

```bash
docker compose up -d qdrant     # http://localhost:6333
```

Для разработки без Docker можно указать `QDRANT_URL=:memory:` (встроенный
режим, примеры живут до перезапуска процесса) или локальный путь
(`QDRANT_URL=./data/qdrant` — с сохранением на диск).

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # указать LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173, /api проксируется на :8000
```

### Наполнение базы примеров

База пополняется фоновым заданием: положите реальные ТЗ (.docx / .md / .txt)
в папку из настройки `EXAMPLES_DIR` (по умолчанию `backend/data/examples`,
сканируется рекурсивно). Раз в `EXAMPLES_SCAN_INTERVAL_SECONDS` (по умолчанию
60 с) задание синхронизирует базу с папкой:

- новые и изменённые файлы (пере)индексируются — изменения отслеживаются по
  sha256 содержимого, хэш хранится в payload Qdrant и переживает перезапуск;
- файлы, удалённые из папки, удаляются и из базы.

Текущий размер базы: `GET /api/examples/stats`.

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| POST | `/api/sessions` | создать сессию (thread LangGraph) |
| POST | `/api/sessions/{id}/messages` | сообщение в чат → `{reply, spec_markdown}` |
| POST | `/api/sessions/{id}/messages/stream` | то же, но SSE-стрим: `token`, `status`, `spec`, `done`, `error` |
| POST | `/api/sessions/{id}/spec/upload` | положить существующее ТЗ в документ (multipart, без LLM) |
| GET | `/api/sessions/{id}/spec` | текущий Markdown документа |
| GET | `/api/examples/stats` | число чанков в базе примеров |

## Деплой в Kubernetes

Всё необходимое лежит в `k8s/` (kustomize): namespace, ConfigMap, Secret,
Deployment'ы backend/frontend, StatefulSet Qdrant с PVC, PVC для папки
примеров и Ingress.

Схема: Ingress → frontend (nginx: статика + прокси `/api` на сервис
`backend:8000`) → backend → Qdrant и LLM-шлюз.

```bash
# 1. Собрать и запушить образы (docker или podman)
docker build -t <registry>/abap-spec-assist/backend:v0.1.0 backend
docker build -t <registry>/abap-spec-assist/frontend:v0.1.0 frontend
docker push <registry>/abap-spec-assist/backend:v0.1.0
docker push <registry>/abap-spec-assist/frontend:v0.1.0

# 2. Указать свои образы/тег
cd k8s && kustomize edit set image \
  abap-spec-assist/backend=<registry>/abap-spec-assist/backend:v0.1.0 \
  abap-spec-assist/frontend=<registry>/abap-spec-assist/frontend:v0.1.0

# 3. Настроить окружение
#    - k8s/configmap.yaml: LLM_BASE_URL, модели и т.д.
#    - k8s/secret.yaml:    LLM_API_KEY (или создать секрет вручную)
#    - k8s/ingress.yaml:   host

# 4. Применить
kubectl apply -k k8s/

# 5. Наполнить базу примеров: скопировать реальные ТЗ в PVC —
#    фоновое задание проиндексирует их само
kubectl -n abap-spec-assist cp ./примеры_тз/. \
  $(kubectl -n abap-spec-assist get pod -l app=backend -o name | cut -d/ -f2):/data/examples/
```

Особенности:

- `backend` намеренно в 1 реплику: сессии чата живут в памяти процесса
  (`MemorySaver`), а PVC примеров — RWO. Для масштабирования нужны общий
  чекпоинтер (postgres) и RWX-том.
- Проба готовности/живости бэкенда — `GET /api/health`; фронтенд стартует и
  до появления бэкенда (nginx резолвит имя сервиса в рантайме, а не на старте).
- Frontend-образ универсален: адрес бэкенда задаётся env `BACKEND_URL`.

## Ограничения / что дальше

- Чекпоинтер in-memory (`MemorySaver`) — сессии живут до перезапуска процесса;
  для продакшена заменить на `langgraph-checkpoint-sqlite`/`-postgres`.
- Экспорт пока только в `.md`; экспорт в `.docx` можно добавить через `docxtpl`.

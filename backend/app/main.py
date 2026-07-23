import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel

from app import auth, spec_doc
from app import sessions as sessions_store
from app.config import settings
from app.docx_parse import file_to_markdown, markdown_to_docx
from app.graph.builder import DOC_WRITE_TOOLS, build_graph
from app.mcp_tools import load_sap_tools
from app.rag import section_index_store
from app.rag.ingest import ingest_example
from app.rag.store import delete_doc, list_docs

logging.basicConfig(level=logging.INFO)

graph = None  # собирается в lifespan — нужен открытый чекпоинтер (см. ниже)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global graph
    Path(settings.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
    # SQLite-чекпоинтер переживает перезапуск процесса — пользователь может
    # вернуться к ТЗ позже (см. app/sessions.py: владелец/заголовок сессии)
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
        await checkpointer.setup()
        # граф пересобирается с SAP-инструментами MCP до приёма трафика
        graph = build_graph(checkpointer, sap_tools=await load_sap_tools())
        yield


app = FastAPI(title="ABAP Spec Assist", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _config(session_id: str) -> dict:
    return {
        "configurable": {"thread_id": session_id},
        "recursion_limit": settings.graph_recursion_limit,
    }


# Правки, внесённые до срыва, уже в чекпоинте — поэтому «продолжите», а не «повторите»
_RECURSION_DETAIL = (
    "Ход остановлен: агент превысил лимит шагов "
    f"({settings.graph_recursion_limit}). Уже внесённые правки сохранены — "
    "попросите продолжить следующим сообщением."
)


async def _current_sections(session_id: str) -> list[dict]:
    snapshot = await graph.aget_state(_config(session_id))
    return snapshot.values.get("sections", []) if snapshot.values else []


async def _current_spec(session_id: str) -> str:
    return spec_doc.render_markdown(await _current_sections(session_id))


async def _prune_checkpoints(session_id: str) -> None:
    """Оставляет последние checkpoint_keep_last чекпоинтов сессии.

    Каждый чекпоинт — полная копия состояния (для большого ТЗ — мегабайты),
    LangGraph сам старые не удаляет. Вызывается после завершения хода, когда
    промежуточные шаги уже не нужны; сбой подрезки не влияет на ответ.
    """
    try:
        saver = graph.checkpointer
        async with saver.lock:
            for table in ("checkpoints", "writes"):
                await saver.conn.execute(
                    f"DELETE FROM {table} WHERE thread_id = ? AND checkpoint_id NOT IN ("
                    "SELECT checkpoint_id FROM checkpoints WHERE thread_id = ? "
                    "ORDER BY checkpoint_id DESC LIMIT ?)",
                    (session_id, session_id, settings.checkpoint_keep_last),
                )
            await saver.conn.commit()
    except Exception:  # noqa: BLE001 — подрезка вспомогательная, ход уже завершён
        logging.getLogger(__name__).warning(
            "Не удалось подрезать чекпоинты сессии %s", session_id, exc_info=True
        )


async def _history(session_id: str) -> list[dict]:
    snapshot = await graph.aget_state(_config(session_id))
    messages = snapshot.values.get("messages", []) if snapshot.values else []
    history = []
    for m in messages:
        if isinstance(m, HumanMessage) and isinstance(m.content, str) and m.content:
            history.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage) and isinstance(m.content, str) and m.content:
            history.append({"role": "assistant", "content": m.content})
    return history


def require_session_owner(
    session_id: str, username: str = Depends(auth.require_user)
) -> str:
    if sessions_store.owner(session_id) != username:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return username


async def _run_graph(session_id: str, user_text: str) -> dict:
    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=user_text)]}, _config(session_id)
        )
    except GraphRecursionError as exc:
        raise HTTPException(status_code=502, detail=_RECURSION_DETAIL) from exc
    except Exception as exc:  # noqa: BLE001 — ошибки шлюза LLM отдаём клиенту как 502
        raise HTTPException(status_code=502, detail=f"Ошибка LLM: {exc}") from exc
    return {
        "reply": result["messages"][-1].content,
        "spec_markdown": spec_doc.render_markdown(result.get("sections", [])),
    }


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class SessionMeta(BaseModel):
    id: str
    title: str
    created_at: float
    updated_at: float


class RenameIn(BaseModel):
    title: str


class MessageIn(BaseModel):
    content: str


class ChatOut(BaseModel):
    reply: str
    spec_markdown: str


class SpecSection(BaseModel):
    id: str
    body: str


class SpecOut(BaseModel):
    spec_markdown: str
    # Разделы отдельно: фронтенд ведёт карту id→текст и применяет дельты из
    # SSE-стрима, не получая полный документ на каждую правку
    sections: list[SpecSection]


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryOut(BaseModel):
    messages: list[HistoryMessage]


class ExampleDocOut(BaseModel):
    name: str
    # Ключ документа в базе (для удаления). Для загруженных через UI совпадает
    # с именем файла; у документов, проиндексированных старым фоновым сканом
    # папки, — это путь файла.
    source: str
    chunks: int


class ExampleUploadResult(BaseModel):
    name: str
    chunks: int = 0
    error: str | None = None


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=UserOut)
def login(body: LoginIn, response: Response) -> UserOut:
    if not settings.auth_enabled:
        return UserOut(username="dev")
    try:
        auth.authenticate(body.username, body.password)
    except auth.LdapAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    token = auth.create_access_token(body.username)
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return UserOut(username=body.username)


@app.post("/api/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=UserOut)
def me(username: str = Depends(auth.require_user)) -> UserOut:
    return UserOut(username=username)


@app.post("/api/sessions", response_model=SessionMeta)
def create_session(username: str = Depends(auth.require_user)) -> SessionMeta:
    return SessionMeta(**sessions_store.create(username))


@app.get("/api/sessions", response_model=list[SessionMeta])
def list_sessions(username: str = Depends(auth.require_user)) -> list[SessionMeta]:
    return [SessionMeta(**s) for s in sessions_store.list_for_user(username)]


@app.patch("/api/sessions/{session_id}")
def rename_session(
    session_id: str, body: RenameIn, username: str = Depends(require_session_owner)
) -> dict:
    if not sessions_store.rename(session_id, username, body.title):
        raise HTTPException(status_code=422, detail="Пустой заголовок")
    return {"status": "ok"}


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str, username: str = Depends(require_session_owner)
) -> dict:
    sessions_store.delete(session_id, username)
    await graph.checkpointer.adelete_thread(session_id)
    section_index_store.clear(session_id)
    return {"status": "ok"}


def _spec_out(sections: list[dict]) -> SpecOut:
    return SpecOut(
        spec_markdown=spec_doc.render_markdown(sections),
        sections=[SpecSection(id=s["id"], body=s["body"]) for s in sections],
    )


@app.get("/api/sessions/{session_id}/spec", response_model=SpecOut)
async def get_spec(session_id: str, _: str = Depends(require_session_owner)) -> SpecOut:
    return _spec_out(await _current_sections(session_id))


@app.get("/api/sessions/{session_id}/spec/export")
async def export_spec(session_id: str, _: str = Depends(require_session_owner)) -> Response:
    """Отдаёт документ ТЗ в .docx — превью в Markdown, но пользователю нужен
    файл в исходном формате, чтобы дальше работать с ним в Word."""
    markdown = await _current_spec(session_id)
    if not markdown:
        raise HTTPException(status_code=404, detail="Документ пуст")
    data = markdown_to_docx(markdown)
    filename = f"{sessions_store.title(session_id) or 'ТЗ'}.docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"tz.docx\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@app.get("/api/sessions/{session_id}/messages", response_model=HistoryOut)
async def get_history(
    session_id: str, _: str = Depends(require_session_owner)
) -> HistoryOut:
    return HistoryOut(messages=[HistoryMessage(**m) for m in await _history(session_id)])


@app.post("/api/sessions/{session_id}/messages", response_model=ChatOut)
async def send_message(
    session_id: str, message: MessageIn, _: str = Depends(require_session_owner)
) -> ChatOut:
    if not message.content.strip():
        raise HTTPException(status_code=422, detail="Пустое сообщение")
    sessions_store.set_title_if_default(session_id, message.content)
    result = await _run_graph(session_id, message.content)
    sessions_store.touch(session_id)
    await _prune_checkpoints(session_id)
    return ChatOut(**result)


@app.post("/api/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: str, message: MessageIn, _: str = Depends(require_session_owner)
) -> StreamingResponse:
    """SSE-стрим хода ассистента.

    События: token (кусок текста ответа), status=updating_spec (агент вызвал
    инструмент), spec (дельта документа: порядок разделов + изменившиеся
    тела — полный текст на каждую правку не гоняется), done (финал), error.
    """
    if not message.content.strip():
        raise HTTPException(status_code=422, detail="Пустое сообщение")
    sessions_store.set_title_if_default(session_id, message.content)
    config = _config(session_id)

    async def gen():
        last_status = None
        prev_bodies = {s["id"]: s["body"] for s in await _current_sections(session_id)}
        try:
            async for mode, chunk in graph.astream(
                {"messages": [HumanMessage(content=message.content)]},
                config,
                stream_mode=["messages", "updates"],
            ):
                if mode == "messages":
                    msg, meta = chunk
                    if meta.get("langgraph_node") != "assistant" or not isinstance(
                        msg, AIMessageChunk
                    ):
                        continue
                    for tc in msg.tool_call_chunks or []:
                        name = tc.get("name")
                        if not name or name == last_status:
                            continue
                        last_status = name
                        if name in DOC_WRITE_TOOLS:
                            yield _sse({"type": "status", "value": "updating_spec"})
                        elif name in (
                            "list_sections",
                            "get_sections",
                            "find_in_document",
                            "find_style_examples",
                        ):
                            continue  # чтение/поиск по документу и примерам — тихо
                        else:
                            yield _sse(
                                {"type": "status", "value": "sap_lookup", "tool": name}
                            )
                    if isinstance(msg.content, str) and msg.content:
                        yield _sse({"type": "token", "text": msg.content})
                else:  # updates
                    for node, update in chunk.items():
                        if node == "tools" and update and "sections" in update:
                            secs = update["sections"]
                            changed = {
                                s["id"]: s["body"]
                                for s in secs
                                if prev_bodies.get(s["id"]) != s["body"]
                            }
                            prev_bodies = {s["id"]: s["body"] for s in secs}
                            yield _sse(
                                {
                                    "type": "spec",
                                    "order": [s["id"] for s in secs],
                                    "changed": changed,
                                }
                            )
        except GraphRecursionError:
            logging.getLogger(__name__).warning(
                "Сессия %s: превышен recursion_limit графа", session_id
            )
            yield _sse({"type": "error", "detail": _RECURSION_DETAIL})
            return
        except Exception as exc:  # noqa: BLE001 — стрим уже начат, отдаём ошибку событием
            logging.getLogger(__name__).exception("Ошибка стрима LLM")
            yield _sse({"type": "error", "detail": f"Ошибка LLM: {exc}"})
            return
        state = await graph.aget_state(config)
        reply = ""
        for m in reversed(state.values.get("messages", [])):
            if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content:
                reply = m.content
                break
        sessions_store.touch(session_id)
        await _prune_checkpoints(session_id)
        # Полный текст в done не шлём — фронтенд собрал документ из дельт;
        # order позволяет ему заметить пропущенную дельту и перезапросить /spec
        yield _sse(
            {
                "type": "done",
                "reply": reply,
                "order": [s["id"] for s in state.values.get("sections", [])],
            }
        )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/sessions/{session_id}/spec/upload", response_model=SpecOut)
async def upload_spec(
    session_id: str, file: UploadFile, _: str = Depends(require_session_owner)
) -> SpecOut:
    """Кладёт приложенное ТЗ в документ сессии (без обращения к LLM).

    Резюме по документу фронтенд запрашивает следом через /messages/stream.
    """
    data = await file.read()
    try:
        markdown = file_to_markdown(file.filename or "file", data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    sections = spec_doc.parse_sections(markdown)
    # Новая загрузка полностью заменяет документ — старый ретривал-кэш неактуален
    await graph.aupdate_state(
        _config(session_id), {"sections": sections, "relevant_section_ids": []}
    )
    section_index_store.clear(session_id)
    sessions_store.set_title_if_default(session_id, file.filename or "Загруженное ТЗ")
    sessions_store.touch(session_id)
    return _spec_out(sections)


# --- база примеров ТЗ (общая для всех пользователей) ---
# Наполняется через UI; фонового скана папки больше нет (см. app/rag/ingest.py).


@app.get("/api/examples", response_model=list[ExampleDocOut])
async def examples_list(_: str = Depends(auth.require_user)) -> list[ExampleDocOut]:
    try:
        docs = await asyncio.to_thread(list_docs)
    except Exception as exc:  # noqa: BLE001 — Qdrant недоступен
        raise HTTPException(status_code=502, detail=f"База примеров недоступна: {exc}") from exc
    return [ExampleDocOut(**d) for d in docs]


@app.post("/api/examples/upload", response_model=list[ExampleUploadResult])
async def examples_upload(
    files: list[UploadFile], _: str = Depends(auth.require_user)
) -> list[ExampleUploadResult]:
    """Индексирует приложенные примеры ТЗ (можно несколько за раз).

    Ключ документа — имя файла: повторная загрузка файла с тем же именем
    заменяет его чанки в базе. Сбой одного файла не прерывает остальные.
    """
    results: list[ExampleUploadResult] = []
    for f in files:
        name = f.filename or "файл"
        data = await f.read()
        try:
            markdown = file_to_markdown(name, data)
            chunks = await asyncio.to_thread(
                ingest_example,
                name,
                markdown,
                source_path=name,
                content_hash=hashlib.sha256(data).hexdigest(),
            )
            results.append(ExampleUploadResult(name=name, chunks=chunks))
        except ValueError as exc:  # неподдерживаемый формат
            results.append(ExampleUploadResult(name=name, error=str(exc)))
        except Exception as exc:  # noqa: BLE001 — эмбеддинги/Qdrant
            results.append(
                ExampleUploadResult(name=name, error=f"Не удалось проиндексировать: {exc}")
            )
    return results


@app.delete("/api/examples")
async def examples_delete(source: str, _: str = Depends(auth.require_user)) -> dict:
    """Удаляет все чанки документа по его ключу (query-параметр source —
    в ключах старых документов из папки есть слэши, path-параметром неудобно)."""
    try:
        await asyncio.to_thread(delete_doc, source)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"База примеров недоступна: {exc}") from exc
    return {"status": "ok"}

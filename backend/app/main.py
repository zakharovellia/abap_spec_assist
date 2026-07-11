import asyncio
import contextlib
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from pydantic import BaseModel

from app.config import settings
from app.docx_parse import file_to_markdown
from app.graph.builder import build_graph
from app.mcp_tools import load_sap_tools
from app.rag.store import count_examples
from app.rag.watcher import watch_examples_dir

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # граф пересобирается с SAP-инструментами MCP до приёма трафика
    global graph
    graph = build_graph(sap_tools=await load_sap_tools())
    watcher = asyncio.create_task(watch_examples_dir())
    yield
    watcher.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await watcher


app = FastAPI(title="ABAP Spec Assist", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = build_graph()


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _current_spec(session_id: str) -> str:
    snapshot = graph.get_state(_config(session_id))
    return snapshot.values.get("spec_markdown", "") if snapshot.values else ""


async def _run_graph(session_id: str, user_text: str) -> dict:
    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=user_text)]}, _config(session_id)
        )
    except Exception as exc:  # noqa: BLE001 — ошибки шлюза LLM отдаём клиенту как 502
        raise HTTPException(status_code=502, detail=f"Ошибка LLM: {exc}") from exc
    return {
        "reply": result["messages"][-1].content,
        "spec_markdown": result.get("spec_markdown", ""),
    }


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class SessionOut(BaseModel):
    session_id: str


class MessageIn(BaseModel):
    content: str


class ChatOut(BaseModel):
    reply: str
    spec_markdown: str


class SpecOut(BaseModel):
    spec_markdown: str


class ExamplesStatsOut(BaseModel):
    chunks_total: int


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/sessions", response_model=SessionOut)
def create_session() -> SessionOut:
    return SessionOut(session_id=uuid.uuid4().hex)


@app.get("/api/sessions/{session_id}/spec", response_model=SpecOut)
def get_spec(session_id: str) -> SpecOut:
    return SpecOut(spec_markdown=_current_spec(session_id))


@app.post("/api/sessions/{session_id}/messages", response_model=ChatOut)
async def send_message(session_id: str, message: MessageIn) -> ChatOut:
    if not message.content.strip():
        raise HTTPException(status_code=422, detail="Пустое сообщение")
    return ChatOut(**await _run_graph(session_id, message.content))


@app.post("/api/sessions/{session_id}/messages/stream")
async def send_message_stream(session_id: str, message: MessageIn) -> StreamingResponse:
    """SSE-стрим хода ассистента.

    События: token (кусок текста ответа), status=updating_spec (агент вызвал
    инструмент), spec (новая версия документа), done (финал), error.
    """
    if not message.content.strip():
        raise HTTPException(status_code=422, detail="Пустое сообщение")
    config = _config(session_id)

    async def gen():
        last_status = None
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
                        if name == "update_spec":
                            yield _sse({"type": "status", "value": "updating_spec"})
                        else:
                            yield _sse(
                                {"type": "status", "value": "sap_lookup", "tool": name}
                            )
                    if isinstance(msg.content, str) and msg.content:
                        yield _sse({"type": "token", "text": msg.content})
                else:  # updates
                    for node, update in chunk.items():
                        if node == "tools" and update and "spec_markdown" in update:
                            yield _sse(
                                {"type": "spec", "markdown": update["spec_markdown"]}
                            )
        except Exception as exc:  # noqa: BLE001 — стрим уже начат, отдаём ошибку событием
            logging.getLogger(__name__).exception("Ошибка стрима LLM")
            yield _sse({"type": "error", "detail": f"Ошибка LLM: {exc}"})
            return
        state = graph.get_state(config)
        reply = ""
        for m in reversed(state.values.get("messages", [])):
            if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content:
                reply = m.content
                break
        yield _sse(
            {
                "type": "done",
                "reply": reply,
                "spec_markdown": state.values.get("spec_markdown", ""),
            }
        )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/sessions/{session_id}/spec/upload", response_model=SpecOut)
async def upload_spec(session_id: str, file: UploadFile) -> SpecOut:
    """Кладёт приложенное ТЗ в документ сессии (без обращения к LLM).

    Резюме по документу фронтенд запрашивает следом через /messages/stream.
    """
    data = await file.read()
    try:
        markdown = file_to_markdown(file.filename or "file", data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    graph.update_state(_config(session_id), {"spec_markdown": markdown})
    return SpecOut(spec_markdown=markdown)


@app.get("/api/examples/stats", response_model=ExamplesStatsOut)
def examples_stats() -> ExamplesStatsOut:
    try:
        return ExamplesStatsOut(chunks_total=count_examples())
    except Exception:  # noqa: BLE001
        return ExamplesStatsOut(chunks_total=0)

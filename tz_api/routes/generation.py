import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from tz_api.dal import conversations as conv_dal
from tz_api.dal import documents as docs_dal
from tz_api.models import GenerationStartedResponse, StartGenerationRequest

router = APIRouter(prefix="/api/documents/{doc_id}/generation", tags=["generation"])


@router.post("", response_model=GenerationStartedResponse)
async def start_generation(doc_id: str, req: StartGenerationRequest) -> dict:
    doc = await docs_dal.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")

    await conv_dal.add_turn(tz_id=doc_id, role="user", content=req.message)
    await docs_dal.update_document_status(doc_id, "in_review")

    return {
        "tz_id": doc_id,
        "thread_id": doc_id,
        "status": "started",
    }


@router.websocket("/stream")
async def stream_generation(websocket: WebSocket, doc_id: str) -> None:
    await websocket.accept()

    doc = await docs_dal.get_document(doc_id)
    if not doc:
        await websocket.send_text(json.dumps({"event": "error", "detail": "ТЗ не найдено"}))
        await websocket.close()
        return

    try:
        from tz_orchestrator.graph import run_generation_stream

        async for event in run_generation_stream(doc_id=doc_id, document=doc):
            await websocket.send_text(json.dumps(event, ensure_ascii=False, default=str))
        await websocket.send_text(json.dumps({"event": "done"}))
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await websocket.send_text(
            json.dumps({"event": "error", "detail": str(exc)}, ensure_ascii=False)
        )
    finally:
        await websocket.close()

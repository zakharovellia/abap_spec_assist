from fastapi import APIRouter, HTTPException

from tz_api.dal import conversations as dal
from tz_api.dal import documents as docs_dal
from tz_api.models import AddMessageRequest, ConversationTurnResponse
from tz_api.serializers import serialize_turn

router = APIRouter(prefix="/api/documents/{doc_id}/conversation", tags=["conversations"])


@router.get("", response_model=list[ConversationTurnResponse])
async def list_turns(doc_id: str) -> list[dict]:
    if not await docs_dal.get_document(doc_id):
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    rows = await dal.list_turns(doc_id)
    return [serialize_turn(r) for r in rows]


@router.post("", response_model=ConversationTurnResponse)
async def add_turn(doc_id: str, req: AddMessageRequest) -> dict:
    if not await docs_dal.get_document(doc_id):
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    row = await dal.add_turn(
        tz_id=doc_id,
        role=req.role,
        content=req.content,
        agent_name=req.agent_name,
    )
    return serialize_turn(row)

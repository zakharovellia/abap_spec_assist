from fastapi import APIRouter, HTTPException

from tz_api.dal import documents as docs_dal
from tz_api.dal import feedback as dal
from tz_api.models import FeedbackRequest, FeedbackResponse
from tz_api.serializers import serialize_feedback

router = APIRouter(prefix="/api/documents/{doc_id}/feedback", tags=["feedback"])


@router.get("", response_model=list[FeedbackResponse])
async def list_feedback(doc_id: str) -> list[dict]:
    if not await docs_dal.get_document(doc_id):
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    rows = await dal.list_feedback(doc_id)
    return [serialize_feedback(r) for r in rows]


@router.post("", response_model=FeedbackResponse)
async def add_feedback(doc_id: str, req: FeedbackRequest) -> dict:
    if not await docs_dal.get_document(doc_id):
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    row = await dal.add_feedback(
        tz_id=doc_id,
        revision_id=req.revision_id,
        developer_id=req.developer_id,
        rating=req.rating,
        category=req.category,
        comment=req.comment,
    )
    return serialize_feedback(row)

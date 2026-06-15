from fastapi import APIRouter, HTTPException, Query

from tz_api.dal import documents as dal
from tz_api.models import (
    CreateDocumentRequest,
    CreateRevisionRequest,
    DocumentResponse,
    RevisionResponse,
)
from tz_api.serializers import serialize_document, serialize_revision

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse)
async def create_document(req: CreateDocumentRequest) -> dict:
    row = await dal.create_document(
        author_id=req.author_id,
        tz_type=req.tz_type,
        scenario=req.scenario,
        title=req.title,
        parent_object_ref=req.parent_object_ref,
    )
    return serialize_document(row)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    author_id: str | None = None,
    scenario: str | None = None,
    parent_object_ref: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
) -> list[dict]:
    rows = await dal.list_documents(
        author_id=author_id,
        scenario=scenario,
        parent_object_ref=parent_object_ref,
        limit=limit,
        offset=offset,
    )
    return [serialize_document(r) for r in rows]


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str) -> dict:
    row = await dal.get_document(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    return serialize_document(row)


@router.get("/{doc_id}/revisions", response_model=list[RevisionResponse])
async def list_revisions(doc_id: str) -> list[dict]:
    if not await dal.get_document(doc_id):
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    rows = await dal.list_revisions(doc_id)
    return [serialize_revision(r) for r in rows]


@router.post("/{doc_id}/revisions", response_model=RevisionResponse)
async def create_revision(doc_id: str, req: CreateRevisionRequest) -> dict:
    if not await dal.get_document(doc_id):
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    row = await dal.create_revision(
        tz_id=doc_id,
        payload=req.payload,
        research_log=req.research_log,
        critic_report=req.critic_report,
        docx_object_key=req.docx_object_key,
        created_by=req.created_by,
    )
    return serialize_revision(row)

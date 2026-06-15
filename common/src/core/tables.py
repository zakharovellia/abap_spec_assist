from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)

metadata = MetaData()

tz_documents = Table(
    "tz_documents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("author_id", Text, nullable=False),
    Column("tz_type", Text, nullable=False),
    Column("scenario", Text, nullable=False, server_default="new"),
    Column("title", Text),
    Column("parent_object_ref", Text),
    Column("status", Text, nullable=False, server_default="draft"),
    Column("current_revision", String(36)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

tz_revisions = Table(
    "tz_revisions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("tz_id", String(36), ForeignKey("tz_documents.id"), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("research_log", JSON, nullable=False),
    Column("critic_report", JSON),
    Column("docx_object_key", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", Text, nullable=False),
)

tz_conversations = Table(
    "tz_conversations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("tz_id", String(36), ForeignKey("tz_documents.id"), nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text),
    Column("tool_calls", JSON),
    Column("tool_result", JSON),
    Column("agent_name", Text),
    Column("model_used", Text),
    Column("tokens_in", Integer),
    Column("tokens_out", Integer),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

tz_mcp_cache = Table(
    "tz_mcp_cache",
    metadata,
    Column("object_key", Text, primary_key=True),
    Column("payload", JSON, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("ttl_seconds", Integer, nullable=False, server_default="3600"),
)

tz_legacy_attachments = Table(
    "tz_legacy_attachments",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("tz_id", String(36), ForeignKey("tz_documents.id", ondelete="CASCADE"), nullable=False),
    Column("filename", Text, nullable=False),
    Column("object_key", Text, nullable=False),
    Column("parsed_payload", JSON),
    Column("raw_text", Text),
    Column("legacy_date", Text),
    Column("extracted_objects", JSON),
    Column("confidence_low_sections", JSON),
    Column("ingest_status", Text, nullable=False, server_default="pending"),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
)

tz_examples_registry = Table(
    "tz_examples_registry",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("tz_type", Text, nullable=False),
    Column("scenario", Text, nullable=False, server_default="new"),
    Column("section_type", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("source_tz_id", Text),
    Column("source_file", Text),
    Column("quality_score", Float, nullable=False, server_default="1.0"),
    Column("embedding_model", Text, nullable=False),
    Column("embedding_dim", Integer, nullable=False),
    Column("qdrant_indexed_at", DateTime(timezone=True)),
    Column("metadata", JSON),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

tz_feedback = Table(
    "tz_feedback",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("tz_id", String(36), ForeignKey("tz_documents.id"), nullable=False),
    Column("revision_id", String(36), ForeignKey("tz_revisions.id"), nullable=False),
    Column("developer_id", Text, nullable=False),
    Column("rating", Integer),
    Column("category", Text),
    Column("comment", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

tz_llm_calls = Table(
    "tz_llm_calls",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("tz_id", String(36)),
    Column("agent_name", Text),
    Column("model", Text),
    Column("tokens_in", Integer),
    Column("tokens_out", Integer),
    Column("latency_ms", Integer),
    Column("cost", Numeric(10, 4)),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

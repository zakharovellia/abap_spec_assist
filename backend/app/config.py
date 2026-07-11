from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "http://llm-gateway.internal/v1"
    llm_api_key: str = "not-needed"
    llm_model: str = "qwen2.5-32b-instruct"
    llm_temperature: float = 0.2
    llm_timeout_seconds: int = 120

    # Эмбеддинги: пустой base_url/api_key = использовать llm_base_url/llm_api_key
    embeddings_base_url: str = ""
    embeddings_api_key: str = ""
    embeddings_model: str = "multilingual-e5-large"

    # Qdrant: http(s)://host:port, ":memory:" или локальный путь (dev без сервера)
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "tz_examples"
    rag_top_k: int = 4

    # Папка с примерами реальных ТЗ; фоновое задание синхронизирует её с Qdrant
    examples_dir: str = "./data/examples"
    examples_scan_interval_seconds: int = 60

    # MCP-сервер ADT tools (чтение объектов SAP); пустой URL = без SAP-инструментов
    mcp_server_url: str = ""
    mcp_transport: str = "streamable_http"
    mcp_auth_token: str = ""

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()

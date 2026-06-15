import configparser
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "common" / "config" / "settings.ini"


def load_config(path: Path | None = None) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read(path or CONFIG_PATH)
    return parser


_config = load_config()


@dataclass(frozen=True)
class DBSettings:
    url: str


@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    api_key: str
    model_small: str
    model_medium: str
    model_strong: str
    temperature_default: float
    timeout_seconds: int


@dataclass(frozen=True)
class EmbeddingsSettings:
    provider: str
    base_url: str
    api_key: str
    model: str
    dim: int
    local_model: str


@dataclass(frozen=True)
class QdrantSettings:
    url: str
    api_key: str
    collection: str


@dataclass(frozen=True)
class MCPSettings:
    server_url: str
    transport: str
    auth_token: str


@dataclass(frozen=True)
class MinioSettings:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool


@dataclass(frozen=True)
class ExplorerLimits:
    new_max_calls: int
    new_max_tokens: int
    modification_max_calls: int
    modification_max_tokens: int


@dataclass(frozen=True)
class Settings:
    env: str
    tz: str
    db: DBSettings
    llm: LLMSettings
    embeddings: EmbeddingsSettings
    qdrant: QdrantSettings
    mcp: MCPSettings
    minio: MinioSettings
    explorer: ExplorerLimits
    critic_max_iterations: int


def _build_settings(cfg: configparser.ConfigParser) -> Settings:
    return Settings(
        env=cfg.get("common", "env", fallback="dev"),
        tz=cfg.get("common", "tz", fallback="Europe/Moscow"),
        db=DBSettings(
            url=cfg.get("db", "url", fallback="sqlite+aiosqlite:///./data/tz_assist.db"),
        ),
        llm=LLMSettings(
            base_url=cfg.get("llm", "base_url", fallback=""),
            api_key=cfg.get("llm", "api_key", fallback=""),
            model_small=cfg.get("llm", "model_small", fallback=""),
            model_medium=cfg.get("llm", "model_medium", fallback=""),
            model_strong=cfg.get("llm", "model_strong", fallback=""),
            temperature_default=cfg.getfloat("llm", "temperature_default", fallback=0.2),
            timeout_seconds=cfg.getint("llm", "timeout_seconds", fallback=120),
        ),
        embeddings=EmbeddingsSettings(
            provider=cfg.get("embeddings", "provider", fallback="api"),
            base_url=cfg.get("embeddings", "base_url", fallback=""),
            api_key=cfg.get("embeddings", "api_key", fallback=""),
            model=cfg.get("embeddings", "model", fallback="multilingual-e5-large"),
            dim=cfg.getint("embeddings", "dim", fallback=1024),
            local_model=cfg.get(
                "embeddings", "local_model", fallback="intfloat/multilingual-e5-large"
            ),
        ),
        qdrant=QdrantSettings(
            url=cfg.get("qdrant", "url", fallback="http://localhost:6333"),
            api_key=cfg.get("qdrant", "api_key", fallback=""),
            collection=cfg.get("qdrant", "collection", fallback="tz_examples"),
        ),
        mcp=MCPSettings(
            server_url=cfg.get("mcp", "server_url", fallback=""),
            transport=cfg.get("mcp", "transport", fallback="streamable_http"),
            auth_token=cfg.get("mcp", "auth_token", fallback=""),
        ),
        minio=MinioSettings(
            endpoint=cfg.get("minio", "endpoint", fallback="localhost:9000"),
            access_key=cfg.get("minio", "access_key", fallback="minioadmin"),
            secret_key=cfg.get("minio", "secret_key", fallback="minioadmin"),
            bucket=cfg.get("minio", "bucket", fallback="tz-documents"),
            secure=cfg.getboolean("minio", "secure", fallback=False),
        ),
        explorer=ExplorerLimits(
            new_max_calls=cfg.getint("explorer", "new_max_calls", fallback=15),
            new_max_tokens=cfg.getint("explorer", "new_max_tokens", fallback=30000),
            modification_max_calls=cfg.getint("explorer", "modification_max_calls", fallback=25),
            modification_max_tokens=cfg.getint(
                "explorer", "modification_max_tokens", fallback=50000
            ),
        ),
        critic_max_iterations=cfg.getint("critic", "max_iterations", fallback=2),
    )


settings = _build_settings(_config)

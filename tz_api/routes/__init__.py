from tz_api.routes.conversations import router as conversations_router
from tz_api.routes.documents import router as documents_router
from tz_api.routes.feedback import router as feedback_router
from tz_api.routes.generation import router as generation_router

__all__ = [
    "documents_router",
    "conversations_router",
    "generation_router",
    "feedback_router",
]

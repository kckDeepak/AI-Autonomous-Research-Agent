from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.api.routes import router
from app.settings import get_settings
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    settings.assert_required_secrets()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Autonomous Research Agent API",
    )
    app.include_router(router, prefix="/v1")
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)

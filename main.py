from contextlib import asynccontextmanager
from fastapi import FastAPI
from config.settings import Settings
from config.plugin_registry import get_registry
from infrastructure.db.postgres import init_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    init_pool(settings.POSTGRES_URL)
    get_registry()          # warm up plugins (loads embedding model, etc.)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TriLink AI Engine",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from config.settings import Settings
from config.plugin_registry import get_registry, PluginRegistry
from infrastructure.db.postgres import init_pool
from infrastructure.db.mongo import init_mongo
from api.routes import mastery, recommendations, learning_path, content


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    init_pool(settings.POSTGRES_URL)
    init_mongo(settings.MONGO_URL)
    app.state.registry = get_registry()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TriLink AI Engine", version="1.0.0", lifespan=lifespan)

    app.include_router(mastery.router,          prefix="/api/ai")
    app.include_router(recommendations.router,  prefix="/api/ai")
    app.include_router(learning_path.router,    prefix="/api/ai")
    app.include_router(content.router,          prefix="/api/ai")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

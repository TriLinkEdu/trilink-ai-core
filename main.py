from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from config.settings import Settings
from config.plugin_registry import get_registry
from infrastructure.db.postgres import init_pool
from infrastructure.db.mongo import init_mongo
from api.routes import mastery, recommendations, learning_path, content, chat, analytics, ingestion
from api.auth import require_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    try:
        init_pool(settings.POSTGRES_URL)
        print("✓ PostgreSQL connected")
    except Exception as e:
        print(f"⚠ PostgreSQL connection failed: {e}")
        print("⚠ AI engine will run with limited functionality")
    
    try:
        init_mongo(settings.MONGO_URL)
        print("✓ MongoDB connected")
    except Exception as e:
        print(f"⚠ MongoDB connection failed: {e}")
    
    try:
        app.state.registry = get_registry()
        print("✓ Plugin registry initialized")
    except Exception as e:
        print(f"⚠ Plugin registry failed: {e}")
    
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TriLink AI Engine", version="1.0.0", lifespan=lifespan)

    # Health check — no auth (load balancer / Docker healthcheck)
    @app.get("/health")
    def health():
        return {"status": "ok"}

    # All AI routes — protected by API key
    auth = [Depends(require_api_key)]
    app.include_router(mastery.router,         prefix="/api/ai", dependencies=auth)
    app.include_router(recommendations.router, prefix="/api/ai", dependencies=auth)
    app.include_router(learning_path.router,   prefix="/api/ai", dependencies=auth)
    app.include_router(content.router,         prefix="/api/ai", dependencies=auth)
    app.include_router(chat.router,            prefix="/api/ai", dependencies=auth)
    app.include_router(analytics.router,       prefix="/api/ai", dependencies=auth)
    app.include_router(ingestion.router,       prefix="/api/ai", dependencies=auth)

    return app


app = create_app()

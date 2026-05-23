from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from config.settings import Settings
from config.plugin_registry import get_registry
from infrastructure.db.postgres import init_pool
from infrastructure.db.mongo import init_mongo
from fastapi.middleware.cors import CORSMiddleware
from api.routes import mastery, recommendations, learning_path, content, chat, analytics
from api.auth import require_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    init_pool(settings.POSTGRES_URL)
    init_mongo(settings.MONGO_URL)
    app.state.registry = get_registry()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TriLink AI Engine", version="1.0.0", lifespan=lifespan)

    # Enable CORS for browser integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for development; tighten for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    return app


app = create_app()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from config.settings import Settings
from infrastructure.db.postgres import init_pool
from infrastructure.db.mongo import init_mongo
from api.routes import mastery, recommendations, learning_path, content, chat, analytics, ingestion
from api.auth import require_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    init_pool(settings.POSTGRES_URL)
    init_mongo(settings.MONGO_URL)
    app.state.registry = None
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TriLink AI Engine", version="1.0.0", lifespan=lifespan)

    # Enable CORS for browser integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
    app.include_router(ingestion.router,       prefix="/api/ai", dependencies=auth)

    return app


app = create_app()

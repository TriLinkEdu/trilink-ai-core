"""
Plugin Registry — the single place where interface contracts are wired
to concrete implementations. Change a plugin by setting an env variable.

To add a new plugin:
  1. Implement the interface in plugins/<category>/
  2. Add a case here
  3. Set the env var — nothing else changes
"""
from functools import lru_cache

from config.settings import Settings
from core.interfaces.knowledge_tracer import KnowledgeTracer
from core.interfaces.content_generator import ContentGenerator
from core.interfaces.embedder import Embedder
from core.interfaces.recommender import Recommender
from core.exceptions import PluginNotConfiguredError


def _build_tracer(settings: Settings) -> KnowledgeTracer:
    match settings.TRACER_PLUGIN:
        case "bkt":
            from plugins.tracers.bkt_tracer import BKTTracer
            return BKTTracer(settings.bkt_params)
        case _:
            raise PluginNotConfiguredError(f"tracer:{settings.TRACER_PLUGIN}")


def _build_generator(settings: Settings) -> ContentGenerator:
    match settings.GENERATOR_PLUGIN:
        case "groq":
            from plugins.generators.groq_generator import GroqGenerator
            return GroqGenerator(api_key=settings.GROQ_API_KEY)
        # case "gemini":
        #     from plugins.generators.gemini_generator import GeminiGenerator
        #     return GeminiGenerator(api_key=settings.GEMINI_API_KEY)
        case "claude":
            from plugins.generators.claude_generator import ClaudeGenerator
            return ClaudeGenerator(api_key=settings.CLAUDE_API_KEY)
        case "openai":
            from plugins.generators.openai_generator import OpenAIGenerator
            return OpenAIGenerator(api_key=settings.OPENAI_API_KEY)
        case _:
            raise PluginNotConfiguredError(f"generator:{settings.GENERATOR_PLUGIN}")


def _build_embedder(settings: Settings) -> Embedder:
    match settings.EMBEDDER_PLUGIN:
        case "minilm":
            from plugins.embedders.minilm_embedder import MiniLMEmbedder
            return MiniLMEmbedder()
        case _:
            raise PluginNotConfiguredError(f"embedder:{settings.EMBEDDER_PLUGIN}")


def _build_recommender(settings: Settings, embedder: Embedder) -> Recommender:
    match settings.RECOMMENDER_PLUGIN:
        case "vector":
            from plugins.recommenders.vector_recommender import VectorRecommender
            return VectorRecommender(embedder=embedder, db_url=settings.POSTGRES_URL)
        case _:
            raise PluginNotConfiguredError(f"recommender:{settings.RECOMMENDER_PLUGIN}")


class PluginRegistry:
    """Holds all resolved plugin instances. Injected into services."""

    def __init__(self, settings: Settings):
        self.tracer: KnowledgeTracer = _build_tracer(settings)
        self.embedder: Embedder = _build_embedder(settings)
        self.generator: ContentGenerator = _build_generator(settings)
        self.recommender: Recommender = _build_recommender(settings, self.embedder)


@lru_cache(maxsize=1)
def get_registry() -> PluginRegistry:
    """Returns the singleton registry. Called once at startup."""
    return PluginRegistry(Settings())

import pytest
from core.exceptions import (
    TriLinkError,
    MasteryNotFoundError,
    TopicNotFoundError,
    ContentGenerationError,
    EmbeddingError,
    PluginNotConfiguredError,
)
from config.plugin_registry import PluginRegistry
from config.settings import Settings


class TestExceptions:

    def test_all_are_trilink_errors(self):
        errors = [
            MasteryNotFoundError("s1", "t1"),
            TopicNotFoundError("t1"),
            ContentGenerationError("t1", "fail"),
            EmbeddingError("fail"),
            PluginNotConfiguredError("groq"),
        ]
        for e in errors:
            assert isinstance(e, TriLinkError)

    def test_messages_contain_ids(self):
        assert "s1" in str(MasteryNotFoundError("s1", "t1"))
        assert "t1" in str(TopicNotFoundError("t1"))
        assert "t1" in str(ContentGenerationError("t1", "reason"))
        assert "reason" in str(ContentGenerationError("t1", "reason"))

    def test_plugin_not_configured_names_plugin(self):
        e = PluginNotConfiguredError("my_plugin")
        assert "my_plugin" in str(e)


class TestPluginRegistry:

    def test_unknown_tracer_raises(self):
        s = Settings(
            TRACER_PLUGIN="nonexistent",
            POSTGRES_URL="postgresql://x",
            MONGO_URL="mongodb://x",
        )
        with pytest.raises(PluginNotConfiguredError):
            PluginRegistry(s)

    def test_unknown_generator_raises(self):
        s = Settings(
            GENERATOR_PLUGIN="nonexistent",
            POSTGRES_URL="postgresql://x",
            MONGO_URL="mongodb://x",
        )
        with pytest.raises(PluginNotConfiguredError):
            PluginRegistry(s)

    def test_unknown_embedder_raises(self):
        s = Settings(
            EMBEDDER_PLUGIN="nonexistent",
            POSTGRES_URL="postgresql://x",
            MONGO_URL="mongodb://x",
        )
        with pytest.raises(PluginNotConfiguredError):
            PluginRegistry(s)

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # --- Plugin selection (change these to swap implementations) ---
    TRACER_PLUGIN: str = "bkt"
    GENERATOR_PLUGIN: str = "groq"
    EMBEDDER_PLUGIN: str = "minilm"
    RECOMMENDER_PLUGIN: str = "vector"

    # --- Infrastructure ---
    POSTGRES_URL: str = Field(..., description="PostgreSQL connection string")
    MONGO_URL: str = Field(..., description="MongoDB connection string")

    # --- External APIs ---
    GROQ_API_KEY: str = Field(default="", description="Groq API key")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key (fallback)")

    # --- BKT tuning ---
    BKT_P_INIT: float = 0.1
    BKT_P_LEARN: float = 0.3
    BKT_P_SLIP: float = 0.1
    BKT_P_GUESS: float = 0.25

    # --- Thresholds ---
    MASTERY_THRESHOLD: float = 0.70
    RECOMMENDATION_LIMIT: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def bkt_params(self) -> dict:
        return {
            "p_init": self.BKT_P_INIT,
            "p_learn": self.BKT_P_LEARN,
            "p_slip": self.BKT_P_SLIP,
            "p_guess": self.BKT_P_GUESS,
        }

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class Settings(BaseSettings):
    # ZenRows settings
    ZENROWS_API_KEY: str = os.getenv("ZENROWS_API_KEY", "")

    # Queue processing settings
    QUEUE_BATCH_SIZE: int = int(os.getenv("QUEUE_BATCH_SIZE", "100"))

    DOUBAN_RATE_LIMIT_DELAY_SECONDS: float = float(
        os.getenv("DOUBAN_RATE_LIMIT_DELAY_SECONDS", "3600")
    )

    DOUBAN_API_REQUEST_DELAY_MAX_SECONDS: float = float(
        os.getenv("DOUBAN_API_REQUEST_DELAY_MAX_SECONDS", "1")
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class Settings(BaseSettings):
    # ZenRows settings
    ZENROWS_API_KEY: str = os.getenv("ZENROWS_API_KEY", "")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

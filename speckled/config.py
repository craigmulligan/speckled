import os
from pydantic_settings import BaseSettings
import dotenv

dotenv.load_dotenv()


class Config(BaseSettings):
    OPENAI_API_KEY: str = ""


# Load settings
config = Config()

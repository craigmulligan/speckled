from pydantic_settings import BaseSettings
import dotenv

dotenv.load_dotenv()


class Config(BaseSettings):
    OPENAI_KEY: str = ""


# Load settings
config = Config()

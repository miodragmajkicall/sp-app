from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    PROJECT_NAME: str = "sp-app"
    DATABASE_URL: str = "postgresql+psycopg2://sp_app:sp_app@db:5432/sp_app"

settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Nexa Management"
    environment: str = "development"
    debug: bool = True
    database_url: str
    ai_enabled: bool = False
    ai_gateway_url: str = "https://ai.springnexa.in"
    cors_origins: str = "http://localhost:3000"
    jwt_issuer: str = "nexa"
    jwt_audience: str = "nexa-app"
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    access_token_minutes: int = 30
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    
    Attributes:
        app_name: Application name
        environment: Environment (development, staging, production)
        cors_origins: List of allowed CORS origins
        database_url: PostgreSQL database URL
        qdrant_url: Qdrant vector database URL
        redis_url: Redis URL
        openai_api_key: OpenAI API key
        cohere_api_key: Cohere API key
        tavily_api_key: Tavily API key
        notion_token: Notion API token
        jira_base_url: Jira base URL
        jira_email: Jira email
        jira_api_token: Jira API token
        jira_project_key: Jira project key
        jwt_secret: JWT secret key
        fernet_key: Fernet encryption key
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Agentic Company Platform"
    environment: str = "development"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/app"
    qdrant_url: str = "http://localhost:6333"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    cohere_api_key: str = ""
    tavily_api_key: str = ""
    notion_token: str = ""

    ollama_enabled: bool = False
    ollama_base_url: str = "http://ollama:11434/v1"

    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    jwt_secret: str = "dev-only-insecure-secret-change-me-in-production!"
    fernet_key: str = ""

settings = Settings()

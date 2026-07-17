from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    
    Attributes:
        app_name: Application name
        environment: Environment (development, staging, production)
        cors_origins: List of allowed CORS origins
        database_url: PostgreSQL database URL
        database_url_migrations: PostgreSQL database URL for migrations
        default_tenant_id: Default tenant ID
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
        langfuse_public_key: Langfuse project public key (tracing disabled if unset)
        langfuse_secret_key: Langfuse project secret key
        langfuse_host: Langfuse server URL the SDK connects to (internal, e.g. docker network address)
        langfuse_public_host: Browser-reachable Langfuse URL, used to build trace links shown in the UI
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Agentic Company Platform"
    environment: str = "development"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/app"
    database_url_migrations: str = "postgresql+asyncpg://app:app@localhost:5432/app"
    default_tenant_id: str = "00000000-0000-0000-0000-000000000001"
    qdrant_url: str = "http://localhost:6333"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    cohere_api_key: str = ""
    tavily_api_key: str = ""
    notion_token: str = ""

    ollama_enabled: bool = False
    ollama_base_url: str = "http://ollama:11434/v1"

    llm_api_concurrency: int = 50
    llm_local_concurrency: int = 4
    llm_timeout: float = 60.0
    llm_local_timeout: float = 120.0
    llm_max_retries: int = 3

    checkpointer_pool_size: int = 20
    db_pool_size: int = 5
    db_max_overflow: int = 5

    rate_limit_chat: str = "30/minute"
    rate_limit_actions: str = "10/minute"
    rate_limit_storage_uri: str = "redis://localhost:6379/1"

    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    jwt_secret: str = "dev-only-insecure-secret-change-me-in-production!"
    fernet_key: str = ""

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""
    langfuse_public_host: str = ""
    langfuse_trace_retention_days: int = 30

settings = Settings()

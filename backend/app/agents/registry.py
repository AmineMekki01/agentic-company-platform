from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    """Static definition of an agent. Mutable runtime settings (enabled, model, system prompt, connector bindings) live in the agent_settings DB table.
    
    Args:
        slug: Unique identifier for the agent
        name: Human-readable name
        description: Brief description of the agent's purpose
        system_prompt: Optional system prompt override
        default_model: Default model to use
        tools: List of tools available to the agent
    """

    slug: str
    name: str
    description: str
    system_prompt: str | None = None
    default_model: str = "gpt-5-nano"
    tools: list[str] = field(default_factory=list)
    is_orchestrator: bool = False
    routes_to: list[str] = field(default_factory=list)

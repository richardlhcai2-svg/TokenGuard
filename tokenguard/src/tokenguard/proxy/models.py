from pydantic import BaseModel, Field
from typing import Optional


class AnthropicRequest(BaseModel):
    """Minimal representation of an Anthropic Messages API request."""
    model: str
    messages: list[dict]
    max_tokens: int
    system: Optional[list] = Field(default_factory=list)
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop_sequences: Optional[list[str]] = None
    stream: Optional[bool] = False

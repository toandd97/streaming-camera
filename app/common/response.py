"""Small shared response models for endpoints without a domain payload."""
from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Standard message-only API response."""

    message: str

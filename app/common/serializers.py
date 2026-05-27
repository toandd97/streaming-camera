"""Serialization helpers shared by MongoDB-backed repositories."""
from datetime import datetime
from typing import Any, Iterable


def serialize_mongo_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return an API-facing copy of a MongoDB document."""
    if document is None:
        return None

    serialized = dict(document)
    if "_id" in serialized:
        serialized["id"] = str(serialized.pop("_id"))
    return serialized


def isoformat_fields(document: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    """Format selected datetime values for untyped JSON endpoints."""
    serialized = dict(document)
    for field in fields:
        value = serialized.get(field)
        if isinstance(value, datetime):
            serialized[field] = value.isoformat()
    return serialized

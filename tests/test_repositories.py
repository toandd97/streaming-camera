from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.repositories.camera_repository import CameraRepository


@pytest.mark.asyncio
async def test_camera_repository_create_uses_shared_crud_and_serialization():
    db = MagicMock()
    collection = db.__getitem__.return_value
    inserted_id = ObjectId()
    collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=inserted_id))
    collection.find_one = AsyncMock(
        return_value={"_id": inserted_id, "name": "Gate", "enabled": True}
    )

    saved = await CameraRepository(db).create({"name": "Gate", "enabled": True})

    payload = collection.insert_one.await_args.args[0]
    assert "created_at" in payload
    assert "updated_at" in payload
    assert saved["id"] == str(inserted_id)
    assert "_id" not in saved

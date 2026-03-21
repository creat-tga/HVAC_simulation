import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = Field(None, max_length=2000)
    location: str | None = Field(None, max_length=200)


class BatchDeleteRequest(BaseModel):
    ids: list[uuid.UUID]


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    location: str | None = Field(None, max_length=200)


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    location: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    location: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

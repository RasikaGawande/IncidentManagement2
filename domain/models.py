"""Response schemas for ServiceNow incidents."""

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class IncidentAttachment(ApiModel):
    id: str
    file_name: str = Field(alias="fileName")
    content_type: str | None = Field(default=None, alias="contentType")
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    file_content: str | None = Field(default=None, alias="fileContent")


class Incident(ApiModel):
    id: str
    title: str
    service: str
    severity: str
    symptoms: str
    created_at: str | None = Field(default=None, alias="createdAt")
    resolved_at: str | None = Field(default=None, alias="resolvedAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    root_cause: str | None = Field(default=None, alias="rootCause")
    resolution: str | None = None
    logs: str | None = None
    attachments: list[IncidentAttachment] = Field(default_factory=list)

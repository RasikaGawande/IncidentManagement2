"""Request and response schemas used by the HTTP API and services."""
from datetime import datetime
from typing import Literal
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

    def searchable_text(self) -> str:
        return f"title: {self.title}; service: {self.service}; severity: {self.severity}; symptoms: {self.symptoms}"

class DeploymentRecord(ApiModel):
    deployment_id: str = Field(alias="deploymentId")
    service: str
    version: str
    deployed_at: datetime = Field(alias="deployedAt")
    deployed_by: str = Field(alias="deployedBy")
    change_summary: str = Field(alias="changeSummary")
    status: str

class SimilarIncident(ApiModel):
    incident: Incident
    similarity: float

class AgentFinding(ApiModel):
    agent_name: str = Field(alias="agentName")
    status: str
    summary: str
    evidence: str

class IncidentAnalysis(ApiModel):
    incoming_incident: Incident = Field(alias="incomingIncident")
    similar_incidents: list[SimilarIncident] = Field(alias="similarIncidents")
    agent_findings: list[AgentFinding] = Field(alias="agentFindings")
    recommendation: str

class AnalyzeRequest(ApiModel):
    incident: Incident
    limit: int = Field(default=3, ge=1, le=20)

class HealthResponse(ApiModel):
    status: Literal["ok", "starting", "error"]
    historical_incident_count: int = Field(alias="historicalIncidentCount")
    detail: str | None = None

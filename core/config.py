"""Environment-based application settings."""
from dataclasses import dataclass
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True, slots=True)
class Settings:
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_api_version: str
    azure_openai_chat_deployment: str
    azure_openai_embedding_deployment: str
    similarity_threshold: float
    data_directory: Path
    github_repository: str | None
    github_token: str | None
    servicenow_instance_url: str | None
    servicenow_username: str | None
    servicenow_password: str | None
    servicenow_incident_limit: int

    @classmethod
    def from_environment(cls) -> "Settings":
        servicenow_instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
        servicenow_username = os.getenv("SERVICENOW_USERNAME")
        servicenow_password = os.getenv("SERVICENOW_PASSWORD")
        if any((servicenow_instance_url, servicenow_username, servicenow_password)) and not all(
            (servicenow_instance_url, servicenow_username, servicenow_password)
        ):
            raise RuntimeError(
                "SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, and SERVICENOW_PASSWORD "
                "must be configured together."
            )
        return cls(
            azure_openai_endpoint=_required("AZURE_OPENAI_ENDPOINT").rstrip("/"),
            azure_openai_api_key=_required("AZURE_OPENAI_API_KEY"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_openai_chat_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5-mini"),
            azure_openai_embedding_deployment=os.getenv(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
            ),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.85")),
            data_directory=Path(os.getenv("DATA_DIRECTORY", PROJECT_ROOT / "data")),
            github_repository=os.getenv("GITHUB_REPOSITORY"),
            github_token=os.getenv("GITHUB_TOKEN"),
            servicenow_instance_url=servicenow_instance_url.rstrip("/") if servicenow_instance_url else None,
            servicenow_username=servicenow_username,
            servicenow_password=servicenow_password,
            servicenow_incident_limit=int(os.getenv("SERVICENOW_INCIDENT_LIMIT", "200")),
        )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured.")
    return value

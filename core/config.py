"""Environment settings for the ServiceNow incident API."""

from dataclasses import dataclass
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class Settings:
    servicenow_instance_url: str | None
    servicenow_username: str | None
    servicenow_password: str | None
    servicenow_incident_limit: int

    @property
    def has_servicenow_credentials(self) -> bool:
        return all((self.servicenow_instance_url, self.servicenow_username, self.servicenow_password))

    @classmethod
    def from_environment(cls) -> "Settings":
        instance_url = os.getenv("SERVICENOW_INSTANCE_URL", "").strip() or None
        username = os.getenv("SERVICENOW_USERNAME", "").strip() or None
        password = os.getenv("SERVICENOW_PASSWORD", "").strip() or None
        try:
            incident_limit = int(os.getenv("SERVICENOW_INCIDENT_LIMIT", "200"))
        except ValueError:
            incident_limit = 200
        return cls(
            servicenow_instance_url=instance_url.rstrip("/") if instance_url else None,
            servicenow_username=username,
            servicenow_password=password,
            servicenow_incident_limit=incident_limit,
        )

"""File-backed fallback incidents used when ServiceNow is unavailable."""

import json
from pathlib import Path

from domain.models import Incident


class ServiceNowFallbackRepository:
    _FILENAME = "servicenow-fallback-incidents.json"

    def __init__(self, data_directory: Path) -> None:
        self._data_directory = data_directory

    def load_active_incidents(self) -> list[Incident]:
        return self._load("active")

    def load_historical_incidents(self) -> list[Incident]:
        return self._load("historical")

    def _load(self, incident_type: str) -> list[Incident]:
        path = self._data_directory / self._FILENAME
        try:
            with path.open(encoding="utf-8") as file:
                records = json.load(file)[incident_type]
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise RuntimeError(f"ServiceNow fallback data could not be read: {path}") from error
        if not isinstance(records, list):
            raise RuntimeError(f"ServiceNow fallback data is invalid: {path}")
        return [Incident.model_validate(record) for record in records]

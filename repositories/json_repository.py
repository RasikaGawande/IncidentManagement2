"""File-backed repositories for the demo data set."""
import json
from pathlib import Path
from domain.models import DeploymentRecord, Incident

class JsonIncidentRepository:
    def __init__(self, data_directory: Path) -> None:
        self._data_directory = data_directory
    def load_historical_incidents(self) -> list[Incident]:
        return self._read_incidents("historical-incidents.json")
    def load_new_incidents(self) -> list[Incident]:
        return self._read_incidents("new-incident.json")
    def _read_incidents(self, filename: str) -> list[Incident]:
        return [Incident.model_validate(item) for item in self._read_json(filename)]
    def _read_json(self, filename: str) -> list[dict]:
        path = self._data_directory / filename
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError as error:
            raise RuntimeError(f"Required data file is missing: {path}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Data file is not valid JSON: {path}") from error

class DeploymentHistoryRepository:
    def __init__(self, data_directory: Path) -> None:
        self._data_directory = data_directory
    def find_by_service(self, service: str) -> list[DeploymentRecord]:
        path = self._data_directory / "deployment-history.json"
        try:
            with path.open(encoding="utf-8") as file:
                records = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as error:
            raise RuntimeError("Deployment history could not be read.") from error
        return [DeploymentRecord.model_validate(record) for record in records if record["service"].casefold() == service.casefold()]

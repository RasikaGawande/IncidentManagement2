from core.config import PROJECT_ROOT, Settings
from repositories.json_repository import ServiceNowFallbackRepository
from repositories.servicenow_repository import ServiceNowIncidentRepository


def test_fallback_data_contains_active_and_historical_incidents() -> None:
    repository = ServiceNowFallbackRepository(PROJECT_ROOT / "data")

    active = repository.load_active_incidents()
    historical = repository.load_historical_incidents()

    assert active[0].id == "INC-DEMO-ACTIVE-001"
    assert active[0].resolved_at is None
    assert historical[0].id == "INC-DEMO-HISTORICAL-001"
    assert historical[0].resolved_at == "2026-07-22 10:45:00"


def test_servicenow_record_maps_to_incident() -> None:
    result = ServiceNowIncidentRepository._to_incident(
        {
            "number": "INC0010001",
            "short_description": "Checkout requests return 502",
            "description": "Users cannot complete checkout.",
            "close_notes": "Rolled back the release.",
            "close_code": "Software defect",
            "priority": "2 - High",
            "cmdb_ci": "checkout-api",
            "sys_created_on": "2026-07-20 09:00:00",
            "resolved_at": "2026-07-20 10:00:00",
            "sys_updated_on": "2026-07-20 10:30:00",
        }
    )

    assert result.id == "INC0010001"
    assert result.service == "checkout-api"
    assert result.resolved_at == "2026-07-20 10:00:00"


def test_partial_servicenow_configuration_uses_fallback_mode(monkeypatch) -> None:
    monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://instance.example")
    monkeypatch.delenv("SERVICENOW_USERNAME", raising=False)
    monkeypatch.delenv("SERVICENOW_PASSWORD", raising=False)

    assert Settings.from_environment().has_servicenow_credentials is False

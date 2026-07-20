"""ServiceNow Table API adapter for resolved incident history."""

import logging
from typing import Any

import httpx

from domain.models import Incident, IncidentAttachment

logger = logging.getLogger("uvicorn.error")


class ServiceNowIncidentRepository:
    """Loads resolved and closed incidents from a ServiceNow instance."""

    _FIELDS = (
        "sys_id,number,short_description,description,close_notes,close_code,priority,"
        "cmdb_ci,business_service,sys_created_on,resolved_at,sys_updated_on"
    )
    _ATTACHMENT_FIELDS = "sys_id,table_sys_id,file_name,content_type,size_bytes"
    _MAX_TEXT_ATTACHMENT_BYTES = 100_000

    def __init__(self, instance_url: str, username: str, password: str, limit: int = 200) -> None:
        self._instance_url = instance_url.rstrip("/")
        self._auth = (username, password)
        self._limit = limit

    def load_historical_incidents(self) -> list[Incident]:
        return self._load_incidents("active=false^ORDERBYDESCresolved_at")

    def load_active_incidents(self) -> list[Incident]:
        """Load only unresolved active incidents without adding them to historical search."""
        return self._load_incidents("active=true^resolved_atISEMPTY^ORDERBYDESCsys_updated_on")

    def _load_incidents(self, query: str) -> list[Incident]:
        logger.info("Requesting ServiceNow incidents with query=%s and limit=%d", query, self._limit)
        try:
            response = httpx.get(
                f"{self._instance_url}/api/now/table/incident",
                auth=self._auth,
                headers={"Accept": "application/json"},
                params={
                    "sysparm_query": query,
                    "sysparm_limit": self._limit,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                    "sysparm_fields": self._FIELDS,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            records = response.json().get("result", [])
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("ServiceNow incident request failed: %s", error)
            raise RuntimeError(f"ServiceNow incident history could not be loaded: {error}") from error
        attachments_by_incident = self._load_attachments(
            [_display_value(record.get("sys_id")) for record in records]
        )
        incidents = [
            self._to_incident(
                record,
                attachments_by_incident.get(_display_value(record.get("sys_id")), []),
            )
            for record in records
        ]
        logger.info("ServiceNow returned %d incident records", len(incidents))
        return incidents

    def _load_attachments(self, incident_sys_ids: list[str]) -> dict[str, list[IncidentAttachment]]:
        incident_sys_ids = [sys_id for sys_id in incident_sys_ids if sys_id]
        if not incident_sys_ids:
            return {}
        try:
            response = httpx.get(
                f"{self._instance_url}/api/now/table/sys_attachment",
                auth=self._auth,
                headers={"Accept": "application/json"},
                params={
                    "sysparm_query": f"table_name=incident^table_sys_idIN{','.join(incident_sys_ids)}",
                    "sysparm_limit": self._limit * 10,
                    "sysparm_display_value": "false",
                    "sysparm_exclude_reference_link": "true",
                    "sysparm_fields": self._ATTACHMENT_FIELDS,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            records = response.json().get("result", [])
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError(f"ServiceNow attachment metadata could not be loaded: {error}") from error

        attachments: dict[str, list[IncidentAttachment]] = {}
        for record in records:
            incident_sys_id = _display_value(record.get("table_sys_id"))
            if not incident_sys_id:
                continue
            attachment = IncidentAttachment(
                id=_display_value(record.get("sys_id")),
                fileName=_display_value(record.get("file_name")) or "unnamed-attachment",
                contentType=_display_value(record.get("content_type")) or None,
                sizeBytes=_integer_value(record.get("size_bytes")),
                fileContent=self._load_text_attachment_content(record),
            )
            attachments.setdefault(incident_sys_id, []).append(attachment)
        logger.info("ServiceNow returned %d attachment metadata records", len(records))
        return attachments

    def _load_text_attachment_content(self, record: dict[str, Any]) -> str | None:
        """Return a bounded UTF-8 excerpt only for plain-text files."""
        filename = _display_value(record.get("file_name"))
        attachment_id = _display_value(record.get("sys_id"))
        if not filename.casefold().endswith(".txt") or not attachment_id:
            return None
        try:
            response = httpx.get(
                f"{self._instance_url}/api/now/attachment/{attachment_id}/file",
                auth=self._auth,
                timeout=20.0,
            )
            response.raise_for_status()
            content = response.content[: self._MAX_TEXT_ATTACHMENT_BYTES]
            logger.info("Loaded text content for ServiceNow attachment %s", attachment_id)
            return content.decode("utf-8", errors="replace")
        except httpx.HTTPError as error:
            logger.warning("ServiceNow text attachment %s could not be loaded: %s", attachment_id, error)
            return None

    @staticmethod
    def _to_incident(record: dict[str, Any], attachments: list[IncidentAttachment] | None = None) -> Incident:
        title = _display_value(record.get("short_description")) or "ServiceNow incident"
        description = _display_value(record.get("description"))
        close_notes = _display_value(record.get("close_notes"))
        service = (
            _display_value(record.get("cmdb_ci"))
            or _display_value(record.get("business_service"))
            or "unknown-service"
        )
        return Incident(
            id=_display_value(record.get("number")) or "unknown-incident",
            title=title,
            service=service,
            severity=_severity(_display_value(record.get("priority"))),
            symptoms=description or title,
            createdAt=_display_value(record.get("sys_created_on")) or None,
            resolvedAt=_display_value(record.get("resolved_at")) or None,
            updatedAt=_display_value(record.get("sys_updated_on")) or None,
            rootCause=_display_value(record.get("close_code")) or None,
            resolution=close_notes or None,
            attachments=attachments or [],
        )


def _display_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("display_value") or value.get("value")
    return str(value).strip() if value else ""


def _severity(priority: str) -> str:
    """Keep ServiceNow's priority in a compact, model-friendly form."""
    first = priority.strip()[:1]
    return f"P{first}" if first.isdigit() else (priority or "P3")


def _integer_value(value: Any) -> int | None:
    try:
        return int(_display_value(value))
    except ValueError:
        return None

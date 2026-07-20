from __future__ import annotations

import json
import logging
import re

from app.seed import canonical_ids


def _performance_events(caplog) -> list[dict[str, object]]:
    return [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "ambrosia.performance" and record.message.startswith("{")
    ]


async def test_every_api_request_reports_route_database_and_server_timing(
    client,
    caplog,
) -> None:
    with caplog.at_level(logging.INFO, logger="ambrosia.performance"):
        response = await client.get("/api/health", headers={"X-Request-ID": "perf-health"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "perf-health"
    assert "app;dur=" in response.headers["server-timing"]
    assert 'db;dur=' in response.headers["server-timing"]
    assert 'desc="1 queries"' in response.headers["server-timing"]

    event = next(
        item
        for item in _performance_events(caplog)
        if item.get("event") == "http_request" and item.get("request_id") == "perf-health"
    )
    assert event["route"] == "/api/health"
    assert event["method"] == "GET"
    assert event["status_code"] == 200
    assert event["query_count"] == 1
    assert float(event["duration_ms"]) >= float(event["database_ms"])


async def test_dynamic_route_logs_template_without_resource_identifier(client, caplog) -> None:
    login = await client.post("/api/auth/demo/session", json={"persona": "provider"})
    assert login.status_code == 200
    patient_id = str(canonical_ids()["sarah_patient_id"])
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="ambrosia.performance"):
        response = await client.get(
            f"/api/patients/{patient_id}",
            headers={"X-Request-ID": "perf-patient"},
        )

    assert response.status_code == 200
    event = next(
        item
        for item in _performance_events(caplog)
        if item.get("event") == "http_request" and item.get("request_id") == "perf-patient"
    )
    assert event["route"] == "/api/patients/{patient_id}"
    assert patient_id not in json.dumps(event)


async def test_bootstrap_stays_within_query_and_local_latency_budgets(client) -> None:
    login = await client.post("/api/auth/demo/session", json={"persona": "provider"})
    assert login.status_code == 200

    response = await client.get("/api/demo/bootstrap")
    assert response.status_code == 200
    timing = response.headers["server-timing"]
    duration_match = re.search(r"app;dur=([\d.]+)", timing)
    query_match = re.search(r'desc="(\d+) queries"', timing)
    assert duration_match and query_match
    assert float(duration_match.group(1)) < 1_000
    assert int(query_match.group(1)) <= 130

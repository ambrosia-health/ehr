from __future__ import annotations

import httpx

from modal_app import _build_inference_app


async def test_inference_route_injects_request_and_response(monkeypatch) -> None:
    app = _build_inference_app()
    route = app.routes[-1]
    assert route.dependant.request_param_name == "request"
    assert route.dependant.response_param_name == "response"
    assert route.dependant.query_params == []
    assert route.dependant.body_params == []

    monkeypatch.setenv("MODAL_INTERNAL_AUTH_SECRET", "expected-internal-secret")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://modal.test") as client:
        response = await client.post("/", json={})
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}

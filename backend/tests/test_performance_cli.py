from __future__ import annotations

from app.performance_cli import parse_performance_events, render_summary


def test_performance_report_parses_modal_prefixes_and_ranks_routes() -> None:
    lines = [
        '2026-07-17T10:00:00Z {"event":"http_request","method":"GET","route":"/api/health","duration_ms":20,"database_ms":5,"query_count":1}\n',
        'INFO {"event":"http_request","method":"GET","route":"/api/demo/bootstrap","duration_ms":900,"database_ms":700,"query_count":120}\n',
        'unrelated runtime log\n',
    ]
    report = render_summary(parse_performance_events(lines))

    assert report.index("/api/demo/bootstrap") < report.index("/api/health")
    assert "| 900 ms | 900 ms | 900 ms | 700 ms | 120.0 |" in report

from __future__ import annotations

import json
import logging
import os
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

SLOW_REQUEST_MS = 750.0
SLOW_QUERY_MS = 250.0

logger = logging.getLogger("ambrosia.performance")
logger.setLevel(logging.INFO)
if os.environ.get("EXECUTION_PLATFORM", "").lower() == "modal" and not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


@dataclass
class RequestMetrics:
    request_id: str
    started_at: float
    query_count: int = 0
    database_ms: float = 0.0
    slow_query_count: int = 0


@dataclass(frozen=True)
class RequestSummary:
    duration_ms: float
    database_ms: float
    query_count: int
    slow_query_count: int

    @property
    def server_timing(self) -> str:
        return (
            f'app;dur={self.duration_ms:.2f}, '
            f'db;dur={self.database_ms:.2f};desc="{self.query_count} queries"'
        )


_request_metrics: ContextVar[RequestMetrics | None] = ContextVar(
    "ambrosia_request_metrics",
    default=None,
)


def begin_request(request_id: str) -> tuple[RequestMetrics, Token[RequestMetrics | None]]:
    metrics = RequestMetrics(request_id=request_id, started_at=time.perf_counter())
    return metrics, _request_metrics.set(metrics)


def reset_request(token: Token[RequestMetrics | None]) -> None:
    _request_metrics.reset(token)


def record_database_query(duration_ms: float, statement: str, *, failed: bool = False) -> None:
    metrics = _request_metrics.get()
    if metrics is None:
        return
    metrics.query_count += 1
    metrics.database_ms += duration_ms
    if duration_ms < SLOW_QUERY_MS:
        return
    metrics.slow_query_count += 1
    _emit(
        logging.WARNING,
        {
            "event": "slow_database_query",
            "request_id": metrics.request_id,
            "operation": _statement_operation(statement),
            "duration_ms": round(duration_ms, 2),
            "failed": failed,
        },
    )


def finish_request(
    metrics: RequestMetrics,
    *,
    method: str,
    route: str,
    status_code: int,
    environment: str,
    execution_platform: str,
    response_bytes: int | None,
    error_type: str | None = None,
) -> RequestSummary:
    duration_ms = (time.perf_counter() - metrics.started_at) * 1_000
    summary = RequestSummary(
        duration_ms=duration_ms,
        database_ms=metrics.database_ms,
        query_count=metrics.query_count,
        slow_query_count=metrics.slow_query_count,
    )
    payload: dict[str, Any] = {
        "event": "http_request",
        "service": "ambrosia-domain-api",
        "environment": environment,
        "execution_platform": execution_platform,
        "region": os.environ.get("MODAL_REGION", "local"),
        "request_id": metrics.request_id,
        "method": method,
        "route": route,
        "status_code": status_code,
        "duration_ms": round(summary.duration_ms, 2),
        "database_ms": round(summary.database_ms, 2),
        "database_share_pct": round(
            (summary.database_ms / summary.duration_ms) * 100,
            1,
        )
        if summary.duration_ms
        else 0.0,
        "query_count": summary.query_count,
        "slow_query_count": summary.slow_query_count,
    }
    if response_bytes is not None:
        payload["response_bytes"] = response_bytes
    if error_type:
        payload["error_type"] = error_type
    level = (
        logging.ERROR
        if status_code >= 500 or error_type
        else logging.WARNING
        if duration_ms >= SLOW_REQUEST_MS
        else logging.INFO
    )
    _emit(level, payload)
    return summary


def instrument_database_engine(engine: AsyncEngine) -> None:
    sync_engine = engine.sync_engine

    def before_cursor_execute(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        context: Any,
        _executemany: bool,
    ) -> None:
        context._ambrosia_query_started_at = time.perf_counter()
        context._ambrosia_query_statement = statement

    def after_cursor_execute(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        context: Any,
        _executemany: bool,
    ) -> None:
        _finish_database_query(context, statement)

    def handle_error(exception_context: Any) -> None:
        context = exception_context.execution_context
        if context is not None:
            _finish_database_query(
                context,
                getattr(context, "_ambrosia_query_statement", "UNKNOWN"),
                failed=True,
            )

    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    event.listen(sync_engine, "after_cursor_execute", after_cursor_execute)
    event.listen(sync_engine, "handle_error", handle_error)


def _finish_database_query(context: Any, statement: str, *, failed: bool = False) -> None:
    started_at = getattr(context, "_ambrosia_query_started_at", None)
    if started_at is None:
        return
    context._ambrosia_query_started_at = None
    record_database_query((time.perf_counter() - started_at) * 1_000, statement, failed=failed)


def _statement_operation(statement: str) -> str:
    normalized = statement.lstrip()
    return normalized.split(None, 1)[0].upper() if normalized else "UNKNOWN"


def _emit(level: int, payload: dict[str, Any]) -> None:
    logger.log(level, json.dumps(payload, separators=(",", ":"), sort_keys=True))

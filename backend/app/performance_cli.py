from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO


def parse_performance_events(lines: Iterable[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in lines:
        start = line.find("{")
        if start < 0:
            continue
        try:
            payload = json.loads(line[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event") == "http_request":
            events.append(payload)
    return events


def render_summary(events: Iterable[dict[str, Any]]) -> str:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[(str(event.get("method", "?")), str(event.get("route", "?")))].append(
            event
        )
    if not grouped:
        raise ValueError("No ambrosia http_request performance events were found")
    rows = [
        "| Route | Count | p50 | p95 | Max | Avg DB | Avg queries |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    ranked = sorted(
        grouped.items(),
        key=lambda item: _percentile([float(row["duration_ms"]) for row in item[1]], 95),
        reverse=True,
    )
    for (method, route), samples in ranked:
        durations = [float(item["duration_ms"]) for item in samples]
        average_db = sum(float(item.get("database_ms", 0)) for item in samples) / len(samples)
        average_queries = sum(int(item.get("query_count", 0)) for item in samples) / len(
            samples
        )
        rows.append(
            f"| `{method} {route}` | {len(samples)} | {_percentile(durations, 50):.0f} ms "
            f"| {_percentile(durations, 95):.0f} ms | {max(durations):.0f} ms "
            f"| {average_db:.0f} ms | {average_queries:.1f} |"
        )
    return "\n".join(rows)


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil((percentile / 100) * len(ordered)) - 1)
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize Ambrosia structured request-performance logs by route."
    )
    parser.add_argument("path", nargs="?", help="Log file; reads stdin when omitted")
    args = parser.parse_args()
    stream: TextIO
    if args.path:
        stream = Path(args.path).open(encoding="utf-8")
    else:
        stream = sys.stdin
    try:
        print(render_summary(parse_performance_events(stream)))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    finally:
        if args.path:
            stream.close()


if __name__ == "__main__":
    main()

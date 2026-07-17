"use client";

import { usePathname } from "next/navigation";
import { useReportWebVitals } from "next/web-vitals";
import { useEffect } from "react";

import {
  normalizeRoute,
  ROUTE_PERFORMANCE_EVENT,
  ROUTE_PERFORMANCE_MEASURE,
  ROUTE_READY_MARK,
  ROUTE_START_MARK,
} from "@/lib/performance";

const reportWebVitals: Parameters<typeof useReportWebVitals>[0] = (metric) => {
  const detail = {
    event: "web_vital",
    route: normalizeRoute(window.location.pathname),
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    navigationType: metric.navigationType,
  };
  window.dispatchEvent(new CustomEvent("ambrosia:web-vital", { detail }));
  if (metric.rating === "poor") console.warn(JSON.stringify(detail));
};

export function PerformanceMonitor() {
  const pathname = usePathname();
  useReportWebVitals(reportWebVitals);

  useEffect(() => {
    let secondFrame = 0;
    const firstFrame = window.requestAnimationFrame(() => {
      secondFrame = window.requestAnimationFrame(() => {
        const route = normalizeRoute(pathname);
        const startMark = performance.getEntriesByName(ROUTE_START_MARK, "mark").at(-1);
        const startedAt = startMark?.startTime ?? 0;
        const endedAt = performance.now();
        const detail = { route, durationMs: Math.max(0, endedAt - startedAt) };
        try {
          performance.measure(ROUTE_PERFORMANCE_MEASURE, {
            start: startedAt,
            end: endedAt,
            detail,
          });
          performance.clearMarks(ROUTE_READY_MARK);
          performance.mark(ROUTE_READY_MARK, { detail: { route } });
        } catch {
          // Route instrumentation must remain inert on browsers without User Timing Level 3.
        }
        window.dispatchEvent(
          new CustomEvent(ROUTE_PERFORMANCE_EVENT, { detail }),
        );
        if (detail.durationMs >= 1_500) {
          console.warn(JSON.stringify({ event: "client_route_transition", ...detail }));
        }
      });
    });
    return () => {
      window.cancelAnimationFrame(firstFrame);
      window.cancelAnimationFrame(secondFrame);
    };
  }, [pathname]);

  return null;
}

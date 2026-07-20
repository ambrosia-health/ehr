export const API_PERFORMANCE_EVENT = "ambrosia:api-performance";
export const API_PERFORMANCE_MEASURE = "ambrosia.api";
export const ROUTE_PERFORMANCE_EVENT = "ambrosia:route-performance";
export const ROUTE_PERFORMANCE_MEASURE = "ambrosia.route-transition";
export const ROUTE_START_MARK = "ambrosia.route-start";
export const ROUTE_READY_MARK = "ambrosia.route-ready";

const SLOW_API_MS = 1_000;
const UUID_SEGMENT = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const OPAQUE_SEGMENT = /^(?:clm|den|enc|msg|pat|task)-[a-z0-9-]{4,}$/i;

export type ApiPerformanceOutcome =
  | "success"
  | "cancelled"
  | "http_error"
  | "network_error"
  | "timeout"
  | "malformed_response"
  | "invalid_content_type";

export interface ApiPerformanceDetail {
  route: string;
  method: string;
  status: number;
  outcome: ApiPerformanceOutcome;
  durationMs: number;
  requestId?: string;
  serverTiming?: string;
}

interface ReportApiPerformanceInput {
  path: string;
  method: string;
  status: number;
  outcome: ApiPerformanceOutcome;
  startedAt: number;
  endedAt: number;
  requestId?: string;
  serverTiming?: string;
}

export function performanceNow(): number {
  return typeof performance === "undefined" ? Date.now() : performance.now();
}

export function normalizeRoute(value: string): string {
  const pathname = value.split(/[?#]/, 1)[0] || "/";
  const segments = pathname.split("/");
  return segments
    .map((segment, index) => {
      if (!segment) return segment;
      const previous = segments[index - 1];
      if (
        UUID_SEGMENT.test(segment)
        || OPAQUE_SEGMENT.test(segment)
        || /^\d+$/.test(segment)
        || previous === "claims"
      ) {
        return ":id";
      }
      return segment;
    })
    .join("/");
}

export function markRouteTransitionStart(url: string, navigationType: string): void {
  if (typeof performance === "undefined" || typeof performance.mark !== "function") return;
  performance.clearMarks(ROUTE_START_MARK);
  performance.mark(ROUTE_START_MARK, {
    detail: { route: normalizeRoute(url), navigationType },
  });
}

export function reportApiPerformance(input: ReportApiPerformanceInput): ApiPerformanceDetail {
  const detail: ApiPerformanceDetail = {
    route: normalizeRoute(input.path),
    method: input.method,
    status: input.status,
    outcome: input.outcome,
    durationMs: Math.max(0, input.endedAt - input.startedAt),
    ...(input.requestId ? { requestId: input.requestId } : {}),
    ...(input.serverTiming ? { serverTiming: input.serverTiming } : {}),
  };

  if (typeof performance !== "undefined" && typeof performance.measure === "function") {
    try {
      performance.measure(API_PERFORMANCE_MEASURE, {
        start: input.startedAt,
        end: input.endedAt,
        detail,
      });
    } catch {
      // User Timing must never affect the request path on older browsers.
    }
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent<ApiPerformanceDetail>(API_PERFORMANCE_EVENT, { detail }));
  }
  if (detail.durationMs >= SLOW_API_MS || !["success", "cancelled"].includes(detail.outcome)) {
    console.warn(JSON.stringify({ event: "client_api_request", ...detail }));
  }
  return detail;
}

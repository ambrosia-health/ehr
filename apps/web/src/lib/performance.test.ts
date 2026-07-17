import { describe, expect, it, vi } from "vitest";

import {
  API_PERFORMANCE_EVENT,
  normalizeRoute,
  reportApiPerformance,
} from "@/lib/performance";

describe("performance instrumentation", () => {
  it.each([
    ["/rcm/claims/CLM-29384?tab=events", "/rcm/claims/:id"],
    ["/api/patients/0b543e6a-a769-4fc4-982b-57e0e3dd25a1", "/api/patients/:id"],
    ["/messages#inbox", "/messages"],
  ])("normalizes high-cardinality route %s", (input, expected) => {
    expect(normalizeRoute(input)).toBe(expected);
  });

  it("emits a browser event with correlation and server timing", () => {
    const listener = vi.fn();
    window.addEventListener(API_PERFORMANCE_EVENT, listener);
    const detail = reportApiPerformance({
      path: "/api/claims/CLM-29384/correct-and-resubmit",
      method: "POST",
      status: 200,
      outcome: "success",
      startedAt: 100,
      endedAt: 145.5,
      requestId: "request-123",
      serverTiming: 'app;dur=40.00, db;dur=25.00;desc="3 queries"',
    });
    window.removeEventListener(API_PERFORMANCE_EVENT, listener);

    expect(detail).toMatchObject({
      route: "/api/claims/:id/correct-and-resubmit",
      durationMs: 45.5,
      requestId: "request-123",
    });
    expect(listener).toHaveBeenCalledOnce();
    expect((listener.mock.calls[0][0] as CustomEvent).detail).toEqual(detail);
  });
});

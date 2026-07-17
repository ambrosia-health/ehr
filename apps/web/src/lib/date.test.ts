import { describe, expect, it } from "vitest";

import { formatInTimeZone } from "@/lib/date";

describe("formatInTimeZone", () => {
  it("does not throw when an upstream timestamp is malformed", () => {
    expect(formatInTimeZone("Draft", "America/New_York", { hour: "numeric" })).toBe("Not recorded");
  });

  it("keeps a date-only clinical value on its calendar date", () => {
    expect(formatInTimeZone("2026-03-08", "America/New_York", { month: "short", day: "numeric" })).toBe("Mar 8");
  });
});

import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/client";
import { parseDemoBootstrap } from "@/lib/api/validation";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

describe("parseDemoBootstrap", () => {
  it("accepts the complete product contract", () => {
    expect(parseDemoBootstrap(structuredClone(bootstrapFixture))).toMatchObject({
      session: bootstrapFixture.session,
      organization: bootstrapFixture.organization,
      scenario: bootstrapFixture.scenario,
    });
  });

  it("rejects partial 2xx payloads before components can render stale assumptions", () => {
    expect(() => parseDemoBootstrap({ session: { authenticated: true } })).toThrowError(ApiError);
    try {
      parseDemoBootstrap({ session: { authenticated: true } });
    } catch (error) {
      expect(error).toMatchObject({ status: 502, message: "The API returned an invalid workspace response." });
    }
  });
});

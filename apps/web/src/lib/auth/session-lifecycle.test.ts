import { beforeEach, describe, expect, it } from "vitest";

import {
  demoSessionCookieNames,
  demoSessionEndedStorageKey,
  hasDemoSessionCookie,
  isDemoSessionMarkedEnded,
  markDemoSessionActive,
  markDemoSessionEnded,
} from "@/lib/auth/session-lifecycle";

describe("demo session lifecycle", () => {
  beforeEach(() => window.localStorage.clear());

  it.each(demoSessionCookieNames)("recognizes the protected session cookie %s", (cookieName) => {
    expect(hasDemoSessionCookie(new Map([[cookieName, true]]))).toBe(true);
  });

  it("does not treat unrelated cookies as an authenticated session", () => {
    expect(hasDemoSessionCookie(new Map([["analytics", true]]))).toBe(false);
  });

  it("persists local revocation until a new API-backed session starts", () => {
    markDemoSessionEnded();
    expect(window.localStorage.getItem(demoSessionEndedStorageKey)).toBe("1");
    expect(isDemoSessionMarkedEnded()).toBe(true);

    markDemoSessionActive();
    expect(isDemoSessionMarkedEnded()).toBe(false);
  });
});

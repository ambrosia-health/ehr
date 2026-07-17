import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/lib/api/client";
import { demoSessionEndedStorageKey, demoSessionExpiredEventName } from "@/lib/auth/session-lifecycle";

describe("apiRequest", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("uses same-origin credentialed no-store requests without a persona header", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ ok: boolean }>("/api/demo/bootstrap")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith("/api/demo/bootstrap", expect.objectContaining({ credentials: "include", cache: "no-store" }));
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(headers["X-Demo-Persona"]).toBeUndefined();
  });

  it("surfaces API failures instead of inventing browser state", async () => {
    const expired = vi.fn();
    window.addEventListener(demoSessionExpiredEventName, expired, { once: true });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Session expired" }), { status: 401, headers: { "content-type": "application/json" } })));
    await expect(apiRequest("/api/demo/bootstrap")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "Session expired",
    } satisfies Partial<ApiError>);
    expect(window.localStorage.getItem(demoSessionEndedStorageKey)).toBe("1");
    expect(expired).toHaveBeenCalledOnce();
  });

  it("formats structured validation failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ msg: "Field is required" }, { msg: "Must be positive" }] }), { status: 422, headers: { "content-type": "application/json" } })));
    await expect(apiRequest("/api/intake/submissions")).rejects.toMatchObject({
      status: 422,
      message: "Field is required; Must be positive",
    });
  });

  it.each([
    ["malformed JSON", new Response("{", { status: 200, headers: { "content-type": "application/json" } }), "The API returned malformed JSON."],
    ["non-JSON success", new Response("ok", { status: 200, headers: { "content-type": "text/plain" } }), "The API returned a non-JSON success response."],
  ])("rejects %s", async (_label, response, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    await expect(apiRequest("/api/demo/bootstrap")).rejects.toMatchObject({ status: 502, message });
  });

  it("aborts requests that exceed the client deadline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_path, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    })));
    await expect(apiRequest("/api/demo/bootstrap", { timeoutMs: 1 })).rejects.toMatchObject({
      status: 0,
      message: "The API request timed out. Please try again.",
    });
  });
});

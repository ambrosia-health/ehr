import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/lib/api/client";

describe("apiRequest", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses same-origin credentialed no-store requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ ok: boolean }>("/api/health")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith("/api/health", expect.objectContaining({ credentials: "include", cache: "no-store" }));
  });

  it("surfaces API failures instead of inventing browser state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Session expired" }), { status: 401, headers: { "content-type": "application/json" } })));
    await expect(apiRequest("/api/health")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "Session expired",
    } satisfies Partial<ApiError>);
  });

  it("formats structured validation failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ msg: "Field is required" }, { msg: "Must be positive" }] }), { status: 422, headers: { "content-type": "application/json" } })));
    await expect(apiRequest("/api/health")).rejects.toMatchObject({
      status: 422,
      message: "Field is required; Must be positive",
    });
  });

  it.each([
    ["malformed JSON", new Response("{", { status: 200, headers: { "content-type": "application/json" } }), "The API returned malformed JSON."],
    ["non-JSON success", new Response("ok", { status: 200, headers: { "content-type": "text/plain" } }), "The API returned a non-JSON success response."],
  ])("rejects %s", async (_label, response, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    await expect(apiRequest("/api/health")).rejects.toMatchObject({ status: 502, message });
  });

  it("aborts requests that exceed the client deadline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_path, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    })));
    await expect(apiRequest("/api/health", { timeoutMs: 1 })).rejects.toMatchObject({
      status: 0,
      message: "The API request timed out. Please try again.",
    });
  });

  it("treats caller cancellation as expected control flow", async () => {
    const controller = new AbortController();
    const warning = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_path, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    })));

    const request = apiRequest("/api/demo/learning/console", { signal: controller.signal });
    controller.abort();

    await expect(request).rejects.toMatchObject({ status: 0, message: "The API request was cancelled." });
    expect(warning).not.toHaveBeenCalled();
    warning.mockRestore();
  });
});

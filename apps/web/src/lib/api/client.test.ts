import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/lib/api/client";

describe("apiRequest", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses same-origin credentialed no-store requests without a persona header", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ ok: boolean }>("/api/demo/bootstrap")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith("/api/demo/bootstrap", expect.objectContaining({ credentials: "include", cache: "no-store" }));
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(headers["X-Demo-Persona"]).toBeUndefined();
  });

  it("surfaces API failures instead of inventing browser state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Session expired" }), { status: 401, headers: { "content-type": "application/json" } })));
    await expect(apiRequest("/api/demo/bootstrap")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "Session expired",
    } satisfies Partial<ApiError>);
  });
});

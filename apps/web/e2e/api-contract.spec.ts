import { expect, test } from "@playwright/test";

function observedTiming(response: { headers(): Record<string, string> }) {
  const value = response.headers()["server-timing"] ?? "";
  const duration = value.match(/app;dur=([\d.]+)/);
  const queries = value.match(/desc="(\d+) queries"/);
  expect(duration, `Missing app timing in ${value}`).toBeTruthy();
  expect(queries, `Missing query count in ${value}`).toBeTruthy();
  return {
    durationMs: Number(duration?.[1]),
    queryCount: Number(queries?.[1]),
  };
}

test("same-origin API enforces the supported session and validation contract", async ({ page }, testInfo) => {
  test.setTimeout(120_000);

  const health = await page.request.get("/api/health", { headers: { "X-Request-ID": "playwright-api-canary" } });
  expect(health.status()).toBe(200);
  expect(await health.json()).toMatchObject({ status: "healthy", database: "healthy" });
  expect(health.headers()["cache-control"]).toContain("no-store");
  expect(health.headers()["x-request-id"]).toBe("playwright-api-canary");
  expect(observedTiming(health).queryCount).toBe(1);

  const login = await page.request.post("/api/auth/demo/session", { data: { persona: "patient" } });
  expect(login.status()).toBe(200);
  const setCookie = login.headers()["set-cookie"] ?? "";
  expect(setCookie).toContain("HttpOnly");
  expect(setCookie.toLowerCase()).toContain("samesite=lax");
  if (String(testInfo.project.use.baseURL).startsWith("https://")) {
    expect(setCookie).toContain("__Host-ambrosia_session=");
    expect(setCookie).toContain("Secure");
  }

  const bootstrap = await page.request.get("/api/demo/bootstrap");
  expect(bootstrap.status()).toBe(200);
  expect(await bootstrap.json()).toMatchObject({
    session: { authenticated: true, persona: "patient" },
    organization: { timezone: "America/New_York" },
  });
  const bootstrapTiming = observedTiming(bootstrap);
  expect(bootstrapTiming.queryCount).toBeLessThanOrEqual(150);
  expect(bootstrapTiming.durationMs).toBeLessThan(5_000);

  expect((await page.request.get("/api/rcm")).status()).toBe(403);
  expect((await page.request.post("/api/intake/submissions", { data: {} })).status()).toBe(422);
  expect((await page.request.post("/api/auth/demo/session", { data: { persona: "patient", body: "x".repeat(256 * 1024) } })).status()).toBe(413);

  expect((await page.request.get("/api/healthz")).status()).toBe(404);
  expect((await page.request.post("/api/auth/login", { data: {} })).status()).toBe(404);
  expect((await page.request.get("/api/presenter/bootstrap")).status()).toBe(404);

  const logout = await page.request.post("/api/auth/logout");
  expect(logout.status()).toBe(200);
  expect((await page.request.get("/api/demo/bootstrap")).status()).toBe(401);
});

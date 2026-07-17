import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { proxy } from "@/proxy";

describe("product route proxy", () => {
  it("redirects requests without a demo session cookie", () => {
    const response = proxy(new NextRequest("https://ambrosia.example/command-center"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://ambrosia.example/login");
  });

  it.each(["ambrosia_session", "__Host-ambrosia_session"])("allows the %s cookie", (cookieName) => {
    const response = proxy(new NextRequest("https://ambrosia.example/command-center", {
      headers: { cookie: `${cookieName}=synthetic-session` },
    }));

    expect(response.status).toBe(200);
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });
});

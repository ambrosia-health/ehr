import { useQuery } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PresenterConsole } from "@/components/presenter/presenter-console";
import { AppProviders } from "@/components/system/app-providers";
import { demoBootstrapQueryKey } from "@/lib/api/hooks";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

const push = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api/hooks", () => ({
  demoBootstrapQueryKey: ["demo-bootstrap"],
  useDemoBootstrap: () => ({
    data: {
      ...bootstrapFixture,
      session: { authenticated: true, persona: "owner", presenter: true },
    },
    mode: "live",
    error: null,
    refetch: vi.fn(),
  }),
}));

function PendingBootstrapQuery() {
  useQuery({
    queryKey: demoBootstrapQueryKey,
    queryFn: ({ signal }) => new Promise((resolve) => {
      signal.addEventListener("abort", () => resolve(bootstrapFixture), { once: true });
    }),
  });
  return <PresenterConsole />;
}

describe("PresenterConsole", () => {
  beforeEach(() => {
    push.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ message: "Persona switched" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
  });

  it("opens a chapter without waiting for a stale bootstrap request", async () => {
    const user = userEvent.setup();
    render(
      <AppProviders initialPersona="owner">
        <PendingBootstrapQuery />
      </AppProviders>,
    );

    await user.click(screen.getByTestId("presenter-chapter-6"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/rcm"));
    expect(fetch).toHaveBeenCalledWith(
      "/api/auth/switch",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });
});

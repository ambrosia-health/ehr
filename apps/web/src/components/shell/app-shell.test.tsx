import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell, PatientHeader } from "@/components/shell/app-shell";
import { AppProviders } from "@/components/system/app-providers";
import { ApiError } from "@/lib/api/client";
import type { ApiMode, DemoBootstrap } from "@/lib/api/types";
import { demoSessionEndedStorageKey } from "@/lib/auth/session-lifecycle";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

const { replaceWithLogin } = vi.hoisted(() => ({ replaceWithLogin: vi.fn() }));
let pathname = "/patient/start";
let bootstrapResult: {
  data: DemoBootstrap | undefined;
  mode: ApiMode;
  error: Error | null;
  refetch: () => void;
} = {
  data: { ...bootstrapFixture, session: { authenticated: true, persona: "patient" as const, presenter: false } },
  mode: "live" as const,
  error: null as Error | null,
  refetch: vi.fn(),
};

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));
vi.mock("@/lib/api/hooks", () => ({
  demoBootstrapQueryKey: ["demo-bootstrap"] as const,
  useDemoBootstrap: () => bootstrapResult,
}));
vi.mock("@/lib/auth/session-lifecycle", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/session-lifecycle")>()),
  replaceWithLogin,
}));

describe("AppShell", () => {
  beforeEach(() => {
    pathname = "/patient/start";
    window.localStorage.clear();
    replaceWithLogin.mockReset();
    bootstrapResult = {
      data: { ...bootstrapFixture, session: { authenticated: true, persona: "patient", presenter: false } },
      mode: "live",
      error: null,
      refetch: vi.fn(),
    };
  });

  it("routes the Ambrosia home link to the patient surface", () => {
    render(<AppProviders initialPersona="provider"><PatientHeader /></AppProviders>);
    expect(screen.getByRole("link", { name: "Ambrosia home" })).toHaveAttribute("href", "/patient/start");
  });

  it("ends an ordinary authenticated session through the API before navigating to login", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ authenticated: false }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AppProviders initialPersona="patient"><PatientHeader /></AppProviders>);

    await user.click(screen.getByLabelText("Account menu"));
    await user.click(screen.getByTestId("exit-demo"));

    await waitFor(() => expect(replaceWithLogin).toHaveBeenCalledOnce());
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", expect.objectContaining({ method: "POST", credentials: "include" }));
    expect(window.localStorage.getItem(demoSessionEndedStorageKey)).toBe("1");
  });

  it("protects a workspace revisited after logout when bootstrap returns 401", async () => {
    bootstrapResult = {
      data: undefined,
      mode: "error",
      error: new ApiError("Session expired", 401),
      refetch: vi.fn(),
    };
    pathname = "/command-center";
    render(<AppProviders initialPersona="provider"><AppShell><p>Protected workspace</p></AppShell></AppProviders>);
    await waitFor(() => expect(replaceWithLogin).toHaveBeenCalledOnce());
    expect(screen.queryByText("Protected workspace")).not.toBeInTheDocument();
  });

  it("keeps cached authenticated content hidden when browser history restores after logout", async () => {
    pathname = "/presenter";
    window.localStorage.setItem(demoSessionEndedStorageKey, "1");
    render(<AppProviders initialPersona="owner"><AppShell><p>Cached presenter workspace</p></AppShell></AppProviders>);

    await waitFor(() => expect(replaceWithLogin).toHaveBeenCalledOnce());
    expect(screen.queryByText("Cached presenter workspace")).not.toBeInTheDocument();
  });

  it("rechecks revocation when a pre-logout document returns from the back-forward cache", async () => {
    pathname = "/presenter";
    render(<AppProviders initialPersona="owner"><AppShell><p>Presenter workspace</p></AppShell></AppProviders>);
    expect(await screen.findByText("Presenter workspace")).toBeVisible();

    window.localStorage.setItem(demoSessionEndedStorageKey, "1");
    window.dispatchEvent(new Event("pageshow"));

    await waitFor(() => expect(replaceWithLogin).toHaveBeenCalledOnce());
    expect(screen.queryByText("Presenter workspace")).not.toBeInTheDocument();
  });

  it("closes mobile navigation as soon as a destination is selected", async () => {
    const user = userEvent.setup();
    bootstrapResult = {
      data: { ...bootstrapFixture, session: { authenticated: true, persona: "provider", presenter: false } },
      mode: "live",
      error: null,
      refetch: vi.fn(),
    };
    pathname = "/command-center";
    render(<AppProviders initialPersona="provider"><AppShell><p>Workspace</p></AppShell></AppProviders>);

    await user.click(await screen.findByLabelText("Open navigation"));
    expect(screen.getByRole("dialog")).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Inbox" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginScreen } from "@/components/product/login-screen";
import { AppProviders } from "@/components/system/app-providers";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

describe("LoginScreen", () => {
  beforeEach(() => {
    push.mockReset();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: "Signed in" }), { status: 200, headers: { "content-type": "application/json" } })));
  });

  it("creates a signed patient session before navigation", async () => {
    const user = userEvent.setup();
    render(<AppProviders initialPersona="provider"><LoginScreen /></AppProviders>);
    await user.click(screen.getByTestId("persona-patient"));
    await user.click(screen.getByTestId("enter-demo"));
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/api/auth/demo/session", expect.objectContaining({ method: "POST", credentials: "include" }));
      expect(push).toHaveBeenCalledWith("/patient/start");
    });
  });

  it("keeps presenter authorization separate from a provider login", async () => {
    const user = userEvent.setup();
    render(<AppProviders initialPersona="provider"><LoginScreen /></AppProviders>);
    await user.type(screen.getByLabelText("Presenter access code"), "secret");
    await user.click(screen.getByTestId("enter-demo"));
    expect(await screen.findByText(/starts with the MSO owner persona/i)).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });
});

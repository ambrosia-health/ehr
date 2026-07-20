import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/shell/app-shell";
import { renderWithProductWorkspace } from "@/test/product-workspace";

const apiRequestMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", () => ({
  ApiError: class ApiError extends Error { constructor(message: string, public status: number) { super(message); } },
  apiRequest: apiRequestMock,
}));

let pathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

describe("AppShell", () => {
  beforeEach(() => {
    pathname = "/";
    apiRequestMock.mockReset();
  });

  it("renders one dermatologist workspace with Today as the canonical home", () => {
    renderWithProductWorkspace(<AppShell><p>Dermatologist workspace</p></AppShell>);

    expect(screen.getByText("Dermatologist workspace")).toBeVisible();
    expect(screen.getByRole("banner")).toBeVisible();
    expect(screen.getByLabelText("Current dermatologist")).toHaveTextContent("Dr. Maya Chen");
    expect(screen.getByLabelText("Current dermatologist")).toHaveTextContent("Midtown");
    expect(screen.getByRole("link", { name: "Ambrosia home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Today" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByText(/sign in|persona|presenter/i)).not.toBeInTheDocument();
  });

  it("keeps the patient section active for patient detail routes", () => {
    pathname = "/patients/patient-1";
    renderWithProductWorkspace(<AppShell><p>Sarah Mitchell</p></AppShell>);

    expect(screen.getByRole("link", { name: "Patients" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Today" })).not.toHaveAttribute("aria-current");
  });

  it("closes mobile navigation as soon as a destination is selected", async () => {
    const user = userEvent.setup();
    renderWithProductWorkspace(<AppShell><p>Workspace</p></AppShell>);

    await user.click(screen.getByLabelText("Open navigation"));
    const mobileNavigation = screen.getByRole("dialog");
    expect(mobileNavigation).toBeVisible();
    const practiceLink = within(mobileNavigation).getByRole("link", { name: "Practice" });
    practiceLink.addEventListener("click", (event) => event.preventDefault(), { once: true });
    await user.click(practiceLink);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("exposes only the three durable product destinations", () => {
    renderWithProductWorkspace(<AppShell><p>Workspace</p></AppShell>);

    const navigation = screen.getAllByRole("navigation", { name: "Primary navigation" })[0];
    expect(within(navigation).getAllByRole("link").map((link) => link.textContent)).toEqual(["Today", "Patients", "Practice"]);
  });

  it("opens the institutional command panel with the keyboard shortcut", async () => {
    const user = userEvent.setup();
    apiRequestMock.mockResolvedValue({ output: { headline: "Changing lesion ready for review.", suggestedFocus: ["Review the linked images."] } });
    renderWithProductWorkspace(<AppShell><p>Workspace</p></AppShell>);

    fireEvent.keyDown(window, { key: "k", metaKey: true });
    const commandPanel = await screen.findByRole("dialog");
    expect(within(commandPanel).getByRole("heading", { name: "Ask Ambrosia" })).toBeVisible();

    await user.click(within(commandPanel).getByRole("button", { name: "Prepare my next patient" }));
    await user.click(within(commandPanel).getByRole("button", { name: "Send command" }));
    expect(await within(commandPanel).findByRole("status")).toHaveTextContent("AI run recorded for inspection");
    expect(apiRequestMock).toHaveBeenCalledWith("/api/ai/chart_summary", expect.objectContaining({ method: "POST" }));
  });
});

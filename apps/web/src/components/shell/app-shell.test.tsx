import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/shell/app-shell";

let pathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

describe("AppShell", () => {
  beforeEach(() => {
    pathname = "/";
  });

  it("renders one dermatologist workspace with Today as the canonical home", () => {
    render(<AppShell><p>Dermatologist workspace</p></AppShell>);

    expect(screen.getByText("Dermatologist workspace")).toBeVisible();
    expect(screen.getByRole("banner")).toBeVisible();
    expect(screen.getByLabelText("Current dermatologist")).toHaveTextContent("Dr. Maya Chen");
    expect(screen.getByLabelText("Current dermatologist")).toHaveTextContent("Midtown Dermatology");
    expect(screen.getByRole("link", { name: "Ambrosia home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Today" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByText(/sign in|persona|presenter/i)).not.toBeInTheDocument();
  });

  it("keeps the patient section active for patient detail routes", () => {
    pathname = "/patients/sarah-mitchell";
    render(<AppShell><p>Sarah Mitchell</p></AppShell>);

    expect(screen.getByRole("link", { name: "Patients" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Today" })).not.toHaveAttribute("aria-current");
  });

  it("closes mobile navigation as soon as a destination is selected", async () => {
    const user = userEvent.setup();
    render(<AppShell><p>Workspace</p></AppShell>);

    await user.click(screen.getByLabelText("Open navigation"));
    const mobileNavigation = screen.getByRole("dialog");
    expect(mobileNavigation).toBeVisible();
    const practiceLink = within(mobileNavigation).getByRole("link", { name: "Practice" });
    practiceLink.addEventListener("click", (event) => event.preventDefault(), { once: true });
    await user.click(practiceLink);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("exposes only the three durable product destinations", () => {
    render(<AppShell><p>Workspace</p></AppShell>);

    const navigation = screen.getAllByRole("navigation", { name: "Primary navigation" })[0];
    expect(within(navigation).getAllByRole("link").map((link) => link.textContent)).toEqual(["Today", "Patients", "Practice"]);
  });

  it("opens the institutional command panel with the keyboard shortcut", async () => {
    const user = userEvent.setup();
    render(<AppShell><p>Workspace</p></AppShell>);

    fireEvent.keyDown(window, { key: "k", metaKey: true });
    const commandPanel = await screen.findByRole("dialog");
    expect(within(commandPanel).getByRole("heading", { name: "Ask Ambrosia" })).toBeVisible();

    await user.click(within(commandPanel).getByRole("button", { name: "Prepare my next patient" }));
    await user.click(within(commandPanel).getByRole("button", { name: "Send command" }));
    expect(within(commandPanel).getByRole("status")).toHaveTextContent("No records changed");
  });
});

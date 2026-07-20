import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TodayScreen } from "@/components/platform/today-screen";
import { createProductWorkspace, renderWithProductWorkspace } from "@/test/product-workspace";

const apiRequestMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", () => ({
  ApiError: class ApiError extends Error { constructor(message: string, public status: number) { super(message); } },
  apiRequest: apiRequestMock,
}));

describe("TodayScreen", () => {
  beforeEach(() => apiRequestMock.mockReset());

  it("renders the database-backed clinician and workday snapshot", () => {
    renderWithProductWorkspace(<TodayScreen />);

    expect(screen.getByRole("heading", { name: "Good morning, Maya.", level: 1 })).toBeVisible();
    expect(screen.getByText("1 decision")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Biopsy this changing lesion?" })).toBeVisible();
    expect(screen.getAllByText("2:30 PM")).toHaveLength(2);
    expect(screen.getByText("1 scheduled · 1 summary prepared")).toBeVisible();
  });

  it("persists approval through the encounter endpoint and refreshes the workspace", async () => {
    const user = userEvent.setup();
    apiRequestMock.mockImplementation((path: string) => path === "/api/demo/bootstrap" ? Promise.resolve(createProductWorkspace({ completed: true })) : Promise.resolve({}));
    renderWithProductWorkspace(<TodayScreen />);

    await user.click(screen.getByRole("button", { name: "Approve plan" }));

    expect(apiRequestMock).toHaveBeenCalledWith("/api/encounters/encounter-1/complete", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Sarah Mitchell’s approved plan is moving");
    expect(screen.getByRole("heading", { name: "All decisions are clear." })).toBeVisible();
  });

  it("reveals source evidence without leaving the decision", async () => {
    const user = userEvent.setup();
    renderWithProductWorkspace(<TodayScreen />);

    await user.click(screen.getByRole("button", { name: "View evidence" }));

    expect(screen.getByRole("region", { name: "Evidence summary" })).toHaveTextContent("New irregular pigmentation compared with baseline");
  });
});

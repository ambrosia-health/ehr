import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TodayScreen } from "@/components/platform/today-screen";

describe("TodayScreen", () => {
  it("opens on one prioritized decision and a prepared day", () => {
    render(<TodayScreen />);

    expect(screen.getByRole("heading", { name: "Good morning, Maya.", level: 1 })).toBeVisible();
    expect(screen.getByText("3 decisions · about 8 min")).toBeVisible();
    expect(screen.getByRole("heading", { name: "This lesion changed since her last visit." })).toBeVisible();
    expect(screen.getByText("Everything else is moving")).toBeVisible();
  });

  it("advances immediately to the next clinical decision after approval", async () => {
    const user = userEvent.setup();
    render(<TodayScreen />);

    await user.click(screen.getByRole("button", { name: "Approve plan" }));

    expect(screen.getByRole("status")).toHaveTextContent("Sarah Mitchell’s approved plan is moving");
    expect(screen.getByText("2 decisions · about 6 min")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Jordan’s pathology needs a clinical disposition." })).toBeVisible();
  });

  it("reveals supporting evidence without leaving the decision", async () => {
    const user = userEvent.setup();
    render(<TodayScreen />);

    await user.click(screen.getByRole("button", { name: "View evidence" }));

    expect(screen.getByRole("region", { name: "Evidence summary" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Hide evidence" })).toHaveAttribute("aria-expanded", "true");
  });
});

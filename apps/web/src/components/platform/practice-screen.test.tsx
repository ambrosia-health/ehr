import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PracticeScreen } from "@/components/platform/practice-screen";

describe("PracticeScreen", () => {
  it("summarizes a healthy practice without creating an admin queue", () => {
    render(<PracticeScreen />);

    expect(screen.getByRole("heading", { name: "Practice is running.", level: 1 })).toBeVisible();
    expect(screen.getByText("The work is moving quietly. Nothing needs your attention.")).toBeVisible();

    const operationsSummary = screen.getByRole("region", { name: "Operations summary" });
    expect(within(operationsSummary).getByText("Moving")).toBeVisible();
    expect(within(operationsSummary).getByText("309")).toBeVisible();
    expect(within(operationsSummary).getByText("Waiting externally")).toBeVisible();
    expect(within(operationsSummary).getByText("7")).toBeVisible();
    expect(within(operationsSummary).getByText("Needs you")).toBeVisible();
    expect(screen.getByText("0 safety risks")).toBeVisible();
    expect(screen.getByText("No office work is waiting on you.")).toBeVisible();
  });

  it("shows automation receipts and reveals advanced controls on demand", async () => {
    const user = userEvent.setup();
    render(<PracticeScreen />);

    const automationHealth = screen.getByRole("region", { name: "Automation health" });
    expect(within(automationHealth).getByRole("progressbar", { name: "Front desk automation health" })).toHaveAttribute("aria-valuenow", "100");
    expect(within(automationHealth).getByRole("progressbar", { name: "Clinical preparation automation health" })).toHaveAttribute("aria-valuenow", "99.8");
    expect(screen.getByRole("complementary", { name: "Today's admin receipts" })).toBeVisible();
    expect(screen.getByText("31 routine actions completed today")).toBeVisible();

    const disclosureLabel = screen.getByText("Advanced controls");
    const disclosure = disclosureLabel.closest("details");
    expect(disclosure).not.toHaveAttribute("open");

    await user.click(disclosureLabel);

    expect(disclosure).toHaveAttribute("open");
    expect(within(disclosure as HTMLElement).getByText("100% of actions recorded")).toBeVisible();
  });
});

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PracticeScreen } from "@/components/platform/practice-screen";
import { createProductWorkspace, renderWithProductWorkspace } from "@/test/product-workspace";

describe("PracticeScreen", () => {
  it("derives operations counts from queues and the command center", () => {
    renderWithProductWorkspace(<PracticeScreen />);

    expect(screen.getByRole("heading", { name: "Practice needs review.", level: 1 })).toBeVisible();
    const operationsSummary = screen.getByRole("region", { name: "Operations summary" });
    expect(within(operationsSummary).getByText("Scheduled")).toBeVisible();
    expect(within(operationsSummary).getByText("Open work")).toBeVisible();
    expect(within(operationsSummary).getByText("Needs clinician")).toBeVisible();
    expect(within(operationsSummary).getAllByText("1")).toHaveLength(3);
  });

  it("renders database-calculated automation health and provenance", async () => {
    const user = userEvent.setup();
    renderWithProductWorkspace(<PracticeScreen />, createProductWorkspace({ completed: true }));

    const automationHealth = screen.getByRole("region", { name: "Automation health" });
    expect(within(automationHealth).getByRole("progressbar", { name: "Visit readiness automation health" })).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByRole("complementary", { name: "Recent durable activity" })).toBeVisible();

    await user.click(screen.getByText("Data provenance"));
    expect(screen.getByText("Version 2 · signed")).toBeVisible();
    expect(screen.getByText(/encounters \+ encounter_notes/)).toBeVisible();
  });
});

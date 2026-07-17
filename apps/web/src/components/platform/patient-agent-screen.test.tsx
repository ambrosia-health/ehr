import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PatientAgentScreen } from "@/components/platform/patient-agent-screen";

describe("PatientAgentScreen", () => {
  it("presents one decision, its recommendation, and structured evidence", () => {
    render(<PatientAgentScreen />);

    expect(screen.getByRole("heading", { name: "Sarah Mitchell", level: 1 })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Biopsy this changing lesion?", level: 2 })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Shave biopsy" })).toBeVisible();
    expect(screen.getByText("91%")).toBeVisible();
    expect(screen.getByRole("img", { name: /clinical photograph of Sarah Mitchell's left posterior shoulder lesion/i })).toBeVisible();
    expect(screen.getByRole("img", { name: /dermoscopy image of Sarah Mitchell's left posterior shoulder lesion/i })).toBeVisible();
    expect(screen.getByRole("table")).toBeVisible();
    expect(screen.getByRole("rowheader", { name: /what changed/i })).toBeVisible();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });

  it("releases the prepared work after clinician approval", async () => {
    const user = userEvent.setup();
    render(<PatientAgentScreen />);

    await user.click(screen.getByRole("button", { name: "Approve & release" }));

    expect(screen.getByText("Released just now")).toBeVisible();
    expect(screen.getByText("Six actions advancing")).toBeVisible();
    expect(screen.getByRole("button", { name: "Approved & released" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Modify" })).toBeDisabled();
  });

  it("supports modifying the recommendation before approval", async () => {
    const user = userEvent.setup();
    render(<PatientAgentScreen />);

    await user.click(screen.getByRole("button", { name: "Modify" }));
    const dialog = screen.getByRole("dialog", { name: "Modify biopsy plan" });
    const recommendation = screen.getByLabelText("Recommendation");
    await user.clear(recommendation);
    await user.type(recommendation, "Excisional biopsy after reviewing anticoagulation status.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(dialog).not.toBeInTheDocument();
    expect(screen.getByText("Excisional biopsy after reviewing anticoagulation status.")).toBeVisible();
  });

  it("keeps the rest of the chart in a native disclosure", async () => {
    const user = userEvent.setup();
    render(<PatientAgentScreen />);

    const disclosure = screen.getByText("View full chart").closest("summary");
    expect(disclosure).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Clinical chart" })).not.toBeVisible();

    await user.click(disclosure!);

    expect(screen.getByRole("heading", { name: "Clinical chart" })).toBeVisible();
    expect(screen.getByText("Adhesive tape allergy · active")).toBeVisible();
  });
});

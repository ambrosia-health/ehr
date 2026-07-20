import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PatientAgentScreen } from "@/components/platform/patient-agent-screen";
import { createProductWorkspace, renderWithProductWorkspace } from "@/test/product-workspace";

const apiRequestMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", () => ({
  ApiError: class ApiError extends Error { constructor(message: string, public status: number) { super(message); } },
  apiRequest: apiRequestMock,
}));

describe("PatientAgentScreen", () => {
  beforeEach(() => apiRequestMock.mockReset());

  it("presents the endpoint recommendation and linked database evidence", () => {
    renderWithProductWorkspace(<PatientAgentScreen patientId="patient-1" />);

    expect(screen.getByRole("heading", { name: "Sarah Mitchell", level: 1 })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Biopsy this changing pigmented lesion?", level: 2 })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Perform shave biopsy" })).toBeVisible();
    expect(screen.getByText(/Favor dysplastic nevus/)).toBeVisible();
    expect(screen.getByRole("img", { name: /clinical photograph of Sarah Mitchell's left posterior shoulder lesion/i })).toHaveAttribute("src", expect.stringContaining("sarah-left-posterior-shoulder"));
    expect(screen.getByRole("table")).toBeVisible();
  });

  it("persists and reloads a released encounter", async () => {
    const user = userEvent.setup();
    apiRequestMock.mockImplementation((path: string) => path === "/api/demo/bootstrap" ? Promise.resolve(createProductWorkspace({ completed: true })) : Promise.resolve({}));
    renderWithProductWorkspace(<PatientAgentScreen patientId="patient-1" />);

    await user.click(screen.getByRole("button", { name: "Approve & release" }));

    expect(apiRequestMock).toHaveBeenCalledWith("/api/encounters/encounter-1/complete", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByText("2 actions advancing")).toBeVisible();
    expect(screen.getByRole("button", { name: "Approved & released" })).toBeDisabled();
  });

  it("writes recommendation changes as a new note version", async () => {
    const user = userEvent.setup();
    const revised = "Excisional biopsy after reviewing anticoagulation status.";
    apiRequestMock.mockImplementation((path: string) => path === "/api/demo/bootstrap" ? Promise.resolve(createProductWorkspace({ assessmentPlan: revised })) : Promise.resolve({}));
    renderWithProductWorkspace(<PatientAgentScreen patientId="patient-1" />);

    await user.click(screen.getByRole("button", { name: "Modify" }));
    const recommendation = screen.getByLabelText("Recommendation");
    await user.clear(recommendation);
    await user.type(recommendation, revised);
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(apiRequestMock).toHaveBeenCalledWith("/api/notes/note-1", expect.objectContaining({ method: "PATCH" }));
    expect(await screen.findByText(revised)).toBeVisible();
  });

  it("reveals chart facts returned by the workspace endpoint", async () => {
    const user = userEvent.setup();
    renderWithProductWorkspace(<PatientAgentScreen patientId="patient-1" />);

    await user.click(screen.getByText("View full chart"));

    expect(screen.getByText("Adhesive tape — rash · allergy")).toBeVisible();
    expect(screen.getByText("Will this leave a big scar?")).toBeVisible();
  });
});

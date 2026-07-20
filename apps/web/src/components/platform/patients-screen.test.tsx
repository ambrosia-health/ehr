import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PatientsScreen } from "@/components/platform/patients-screen";
import { renderWithProductWorkspace } from "@/test/product-workspace";

describe("PatientsScreen", () => {
  it("presents the database patient as a compact clinical worklist", () => {
    renderWithProductWorkspace(<PatientsScreen />);

    expect(screen.getByRole("heading", { name: "Patients", level: 1 })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Patients", level: 1 }).closest("header")).toHaveTextContent("1 active journey");
    expect(screen.getByRole("link", { name: "Open Sarah Mitchell" })).toHaveAttribute("href", "/patients/patient-1");
    expect(screen.getByText("Review 2-action plan · now")).toBeVisible();
  });

  it("filters and searches the endpoint result without synthetic fallback rows", async () => {
    const user = userEvent.setup();
    renderWithProductWorkspace(<PatientsScreen />);

    await user.click(screen.getByRole("button", { name: "Waiting" }));
    expect(screen.getByText("No patient matches this view.")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "All" }));
    await user.type(screen.getByRole("textbox", { name: "Search patients" }), "AM-10482");
    expect(screen.getByText("Sarah Mitchell")).toBeVisible();
    expect(screen.getByText("1 of 1 shown")).toBeVisible();
  });
});

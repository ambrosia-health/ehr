import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PatientsScreen } from "@/components/platform/patients-screen";

describe("PatientsScreen", () => {
  it("presents the patient directory as a compact clinical worklist", () => {
    render(<PatientsScreen />);

    expect(screen.getByRole("heading", { name: "Patients", level: 1 })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Patient worklist", level: 2 })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open Sarah Mitchell" })).toHaveAttribute("href", "/patients/sarah-mitchell");
    expect(screen.getByText("Review biopsy plan · now")).toBeVisible();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });

  it("searches and filters without losing concise patient context", async () => {
    const user = userEvent.setup();
    render(<PatientsScreen />);

    await user.click(screen.getByRole("button", { name: "Waiting" }));
    expect(screen.getByRole("button", { name: "Waiting" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Natalie Wong")).toBeVisible();
    expect(screen.getByText("Jordan Lee")).toBeVisible();
    expect(screen.queryByText("Sarah Mitchell")).not.toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "Search patients" }), "psoriasis");
    expect(screen.getByText("Natalie Wong")).toBeVisible();
    expect(screen.queryByText("Jordan Lee")).not.toBeInTheDocument();
  });
});

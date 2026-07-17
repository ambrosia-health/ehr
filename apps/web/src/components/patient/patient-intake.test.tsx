import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PatientIntake } from "@/components/patient/patient-intake";
import { AppProviders } from "@/components/system/app-providers";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

vi.mock("@/lib/api/hooks", () => ({ useDemoBootstrap: () => ({ data: bootstrapFixture, mode: "live", error: null, refetch: vi.fn() }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

describe("PatientIntake", () => {
  it("blocks progression until the concern step is valid", async () => {
    const user = userEvent.setup();
    render(<AppProviders initialPersona="patient"><PatientIntake /></AppProviders>);
    await user.click(screen.getByTestId("intake-next"));
    const reason = screen.getByLabelText("What would you like us to look at?");
    const reasonError = await screen.findByText(/tell us a little more/i);
    expect(reasonError).toHaveAttribute("role", "alert");
    expect(reason).toHaveAttribute("aria-invalid", "true");
    expect(reason).toHaveAttribute("aria-describedby", reasonError.id);
    expect(reason).toHaveFocus();
    await user.type(reason, "A mole changed color recently.");
    await user.selectOptions(screen.getByLabelText("When did you first notice the change?"), "1–3 months ago");
    await user.click(screen.getByTestId("intake-next"));
    const nextHeading = await screen.findByRole("heading", { name: "What have you noticed?" });
    await waitFor(() => expect(nextHeading).toHaveFocus());
  });

  it("keeps same-time provider slots distinct through review", async () => {
    const user = userEvent.setup();
    render(<AppProviders initialPersona="patient"><PatientIntake /></AppProviders>);

    await user.type(screen.getByLabelText("What would you like us to look at?"), "A mole changed color recently.");
    await user.selectOptions(screen.getByLabelText("When did you first notice the change?"), "1–3 months ago");
    await user.click(screen.getByTestId("intake-next"));
    await user.click(screen.getByRole("checkbox", { name: "Darker color" }));
    await user.click(screen.getByRole("checkbox", { name: "No symptoms" }));
    await user.click(screen.getByTestId("intake-next"));

    await user.type(screen.getByLabelText("Current medications"), "None");
    await user.type(screen.getByLabelText("Allergies and reactions"), "None");
    await user.type(screen.getByLabelText("Personal skin-cancer history"), "None");
    await user.type(screen.getByLabelText("Family skin-cancer history"), "None");
    await user.type(screen.getByLabelText("Preferred pharmacy"), "Union Square Pharmacy");
    await user.click(screen.getByTestId("intake-next"));
    expect(screen.getByText("Answer required")).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: "None of these" }));
    await user.click(screen.getByTestId("intake-next"));
    await user.click(screen.getByTestId("intake-next"));

    const sameTimeSlots = screen.getAllByRole("radio");
    expect(sameTimeSlots).toHaveLength(2);
    await user.click(sameTimeSlots[1]!);
    await user.click(screen.getByTestId("intake-next"));
    await user.click(screen.getByTestId("intake-next"));

    expect(await screen.findByText(/Dr\. Imani Okafor · Midtown/)).toBeVisible();
    expect(screen.queryByText(/Dr\. Maya Chen · Union Square/)).not.toBeInTheDocument();
  });

  it("keeps ‘No symptoms’ mutually exclusive with reported symptoms", async () => {
    const user = userEvent.setup();
    render(<AppProviders initialPersona="patient"><PatientIntake /></AppProviders>);
    await user.type(screen.getByLabelText("What would you like us to look at?"), "A mole changed color recently.");
    await user.selectOptions(screen.getByLabelText("When did you first notice the change?"), "1–3 months ago");
    await user.click(screen.getByTestId("intake-next"));

    const itching = screen.getByRole("checkbox", { name: "Itching" });
    const bleeding = screen.getByRole("checkbox", { name: "Bleeding" });
    const none = screen.getByRole("checkbox", { name: "No symptoms" });
    await user.click(itching);
    await user.click(none);
    expect(none).toBeChecked();
    expect(itching).not.toBeChecked();
    await user.click(bleeding);
    expect(bleeding).toBeChecked();
    expect(none).not.toBeChecked();
  });

  it("hydrates stable intake labels and selections from the API draft", async () => {
    const originalDraft = bootstrapFixture.intake!.draft;
    bootstrapFixture.intake!.draft = {
      ...originalDraft,
      reason: "A mole on my shoulder has become wider and darker.",
      firstNoticed: "3–6 months ago",
      change: ["Wider or larger", "Darker color"],
      symptoms: ["Itching"],
    };

    try {
      const user = userEvent.setup();
      render(<AppProviders initialPersona="patient"><PatientIntake /></AppProviders>);
      await waitFor(() => expect(screen.getByLabelText("When did you first notice the change?")).toHaveValue("3–6 months ago"));
      await user.click(screen.getByTestId("intake-next"));
      expect(screen.getByRole("checkbox", { name: "Wider or larger" })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: "Darker color" })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: "Itching" })).toBeChecked();
    } finally {
      bootstrapFixture.intake!.draft = originalDraft;
    }
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EncounterWorkspace } from "@/components/provider/encounter-workspace";
import { AppProviders } from "@/components/system/app-providers";
import type { DemoBootstrap } from "@/lib/api/types";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

const providerBootstrap = {
  ...bootstrapFixture,
  session: { authenticated: true as const, persona: "provider" as const, presenter: false },
};

vi.mock("@/lib/api/hooks", () => ({
  useDemoBootstrap: () => ({ data: providerBootstrap, mode: "live", error: null, refetch: vi.fn() }),
}));

describe("EncounterWorkspace", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("hydrates, saves, and re-renders the durable latest lesion observation", async () => {
    const latest = bootstrapFixture.patient!.lesion.latestObservation;
    const originalLength = latest.lengthMm;
    const fetchMock = vi.fn().mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      latest.lengthMm = body.lengthMm;
      return new Response(JSON.stringify({ observationId: "observation-2", recordedAt: "2026-07-16T10:15:00-04:00" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    try {
      const user = userEvent.setup();
      render(<AppProviders initialPersona="provider"><EncounterWorkspace /></AppProviders>);
      await user.click(screen.getByRole("tab", { name: "Lesion" }));
      const length = screen.getByLabelText("Length (mm)");
      expect(length).toHaveValue(7);
      expect(screen.getByTestId("save-lesion-observation")).toBeDisabled();

      await user.clear(length);
      await user.type(length, "7.2");
      await user.click(screen.getByTestId("save-lesion-observation"));
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      const body = JSON.parse(String(fetchMock.mock.calls[0]![1]!.body));
      expect(body).toMatchObject({
        lesionId: "lesion-1",
        encounterId: "encounter-1",
        lengthMm: 7.2,
        widthMm: 5,
        pigmentation: latest.pigmentation,
        changeOverTime: latest.changeOverTime,
        assessment: latest.assessment,
      });
      await waitFor(() => expect(length).toHaveValue(7.2));
      expect(await screen.findByTestId("lesion-observation-receipt")).toBeVisible();
    } finally {
      latest.lengthMm = originalLength;
    }
  });

  it("keeps coordinator access read-only instead of exposing provider-only mutations", async () => {
    const bootstrap = providerBootstrap as DemoBootstrap;
    const originalSession = bootstrap.session;
    bootstrap.session = { authenticated: true, persona: "clinical", presenter: false };
    try {
      const user = userEvent.setup();
      render(<AppProviders initialPersona="clinical"><EncounterWorkspace /></AppProviders>);
      expect(screen.getByTestId("clinical-read-only")).toBeVisible();
      expect(screen.getByLabelText("Assessment and plan")).toHaveAttribute("readonly");
      expect(screen.getByTestId("review-actions")).toBeDisabled();
      await user.click(screen.getByRole("tab", { name: "Lesion" }));
      expect(screen.getByLabelText("Length (mm)")).toBeDisabled();
      expect(screen.getByTestId("save-lesion-observation")).toBeDisabled();
    } finally {
      bootstrap.session = originalSession;
    }
  });
});

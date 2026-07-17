import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewComplete } from "@/components/provider/review-complete";
import { AppProviders } from "@/components/system/app-providers";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

vi.mock("@/lib/api/hooks", () => ({ useDemoBootstrap: () => ({ data: { ...bootstrapFixture, session: { authenticated: true, persona: "provider", presenter: false } }, mode: "live", error: null, refetch: vi.fn() }) }));

describe("ReviewComplete", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("disables completion when a required proposal is deselected", async () => {
    const user = userEvent.setup();
    render(<AppProviders initialPersona="provider"><ReviewComplete /></AppProviders>);
    const complete = screen.getByTestId("complete-encounter");
    expect(complete).toBeDisabled();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes.at(-1)!);
    await waitFor(() => expect(complete).toBeEnabled());
    const required = checkboxes[0];
    await user.click(required!);
    await waitFor(() => expect(complete).toBeDisabled());
    expect(await screen.findByText(/restore every required action/i)).toBeVisible();
  });

  it("sends the explicit clinician attestation and durable proposal IDs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      encounterId: "encounter-1",
      status: "completed",
      signedAt: "2026-07-16T10:00:00-04:00",
      noteId: "note-1",
      noteVersion: 2,
      consentId: "consent-1",
      procedureId: "procedure-1",
      specimenId: "specimen-1",
      orderId: "order-1",
      claimId: "claim-1",
      messageId: "message-1",
      closureTaskId: "task-1",
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppProviders initialPersona="provider"><ReviewComplete /></AppProviders>);

    await user.click(screen.getAllByRole("checkbox").at(-1)!);
    await user.click(screen.getByTestId("complete-encounter"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const body = JSON.parse(String(fetchMock.mock.calls[0]![1]!.body));
    expect(body).toMatchObject({
      attest: true,
      signNote: true,
      expectedNoteVersion: bootstrapFixture.encounter!.note.currentVersion.number,
      expectedNoteHash: bootstrapFixture.encounter!.note.currentVersion.contentHash,
      attestation: "I reviewed the source record and approve the selected actions.",
    });
    expect(body).not.toHaveProperty("noteDraft");
    expect(body.proposedActionIds).toEqual(bootstrapFixture.encounter!.proposals.map((proposal) => proposal.id));
  });

  it("restores the durable completion receipt instead of offering a second signature", () => {
    const encounter = bootstrapFixture.encounter!;
    const originalStatus = encounter.status;
    const originalNoteStatus = encounter.note.status;
    const originalReceipt = encounter.completionReceipt;
    encounter.status = "signed";
    encounter.note.status = "signed";
    encounter.completionReceipt = {
      status: "completed",
      signedAt: "2026-07-16T10:00:00-04:00",
      noteId: "note-1",
      consentId: "consent-1",
      procedureId: "procedure-1",
      specimenId: "specimen-1",
      orderId: "order-1",
      claimId: "claim-1",
      messageId: "message-1",
      closureTaskId: "task-1",
    };

    try {
      render(<AppProviders initialPersona="provider"><ReviewComplete /></AppProviders>);
      expect(screen.getByTestId("encounter-completion-receipt")).toBeVisible();
      expect(screen.getByText("Consent linked")).toBeVisible();
      expect(screen.getByText("Procedure recorded")).toBeVisible();
      expect(screen.getByText("Closure task created")).toBeVisible();
      expect(screen.queryByTestId("complete-encounter")).not.toBeInTheDocument();
    } finally {
      encounter.status = originalStatus;
      encounter.note.status = originalNoteStatus;
      encounter.completionReceipt = originalReceipt;
    }
  });
});

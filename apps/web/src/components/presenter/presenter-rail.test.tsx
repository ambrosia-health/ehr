import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PresenterRail, presenterActionBlockedReason } from "@/components/presenter/presenter-rail";
import { AppProviders, useDemoSession } from "@/components/system/app-providers";
import type { DemoBootstrap } from "@/lib/api/types";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

vi.mock("next/navigation", () => ({ usePathname: () => "/presenter" }));
vi.mock("@/lib/api/hooks", () => ({
  useDemoBootstrap: () => ({ data: { ...bootstrapFixture, session: { authenticated: true, persona: "owner", presenter: true } }, mode: "live", error: null, refetch: vi.fn() }),
}));

function SessionStateProbe({ onResetComplete }: { onResetComplete: () => void }) {
  const session = useDemoSession();
  return <>
    <button type="button" onClick={() => {
      session.setIntakeTriage({ status: "staff_review", taskId: "task-1", notificationId: "notification-1", readinessStatus: "needs_review" });
      session.updateEncounterReview({ noteDraft: "Unsaved stale note", selectedProposalIds: ["proposal-1"] });
    }}>Mutate session state</button>
    <button type="button" onClick={() => session.setPersona("provider")}>Open provider chapter</button>
    <output data-testid="session-state">{JSON.stringify({ triage: session.intakeTriage, review: session.encounterReview })}</output>
    <PresenterRail onResetComplete={onResetComplete} />
  </>;
}

function presenterState(): DemoBootstrap {
  return structuredClone({
    ...bootstrapFixture,
    session: { authenticated: true, persona: "provider", presenter: true },
  }) as DemoBootstrap;
}

describe("presenter action readiness", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("blocks timeline mutations until encounter completion creates durable dependencies", () => {
    const data = presenterState();
    data.encounter!.completionReceipt = null;
    data.pathology = { ...data.pathology!, id: null, status: "pending" };
    data.claims = [];
    data.triggerIds = { patientId: "patient-1", encounterId: "encounter-1", lesionId: "lesion-1", claimId: null, pathologyResultId: null };

    expect(presenterActionBlockedReason("pathology", data, "live", null)).toMatch(/order and specimen/i);
    expect(presenterActionBlockedReason("claim", data, "live", null)).toMatch(/durable claim/i);
    expect(presenterActionBlockedReason("advance", data, "live", null)).toMatch(/timeline events/i);
    expect(presenterActionBlockedReason("reset", data, "live", null)).toBeNull();
  });

  it("allows eligible staged actions and blocks terminal or out-of-order transitions", () => {
    const data = presenterState();
    data.encounter!.completionReceipt = {
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
    const claim = {
      id: "claim-1",
      status: "draft",
    } as DemoBootstrap["claims"][number];
    data.claims = [claim];
    data.pathology = { ...data.pathology!, id: null, status: "pending" };
    data.triggerIds = { patientId: "patient-1", encounterId: "encounter-1", lesionId: "lesion-1", claimId: claim.id, pathologyResultId: null };

    expect(presenterActionBlockedReason("pathology", data, "live", claim.id)).toBeNull();
    expect(presenterActionBlockedReason("claim", data, "live", claim.id)).toBeNull();
    expect(presenterActionBlockedReason("advance", data, "live", claim.id)).toBeNull();

    claim.status = "denied";
    expect(presenterActionBlockedReason("claim", data, "live", claim.id)).toMatch(/correct and resubmit/i);
    expect(presenterActionBlockedReason("advance", data, "live", claim.id)).toMatch(/events are not consumed/i);

    claim.status = "paid";
    expect(presenterActionBlockedReason("claim", data, "live", claim.id)).toMatch(/already paid/i);
    expect(presenterActionBlockedReason("advance", data, "live", claim.id)).toMatch(/timeline is complete/i);

    data.pathology = { ...data.pathology!, id: "result-1", status: "received" };
    expect(presenterActionBlockedReason("pathology", data, "live", claim.id)).toMatch(/already been delivered/i);
  });

  it("clears ephemeral workflow state before returning to the presenter console after reset", async () => {
    const user = userEvent.setup();
    const onResetComplete = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: "Canonical synthetic scenario restored", at: "2026-07-16T10:00:00Z" }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AppProviders initialPersona="owner"><SessionStateProbe onResetComplete={onResetComplete} /></AppProviders>);

    await user.click(screen.getByRole("button", { name: "Mutate session state" }));
    expect(screen.getByTestId("session-state")).toHaveTextContent("Unsaved stale note");
    await user.click(screen.getByTestId("presenter-rail-toggle"));
    await user.click(screen.getByTestId("presenter-reset"));

    await waitFor(() => expect(onResetComplete).toHaveBeenCalledOnce());
    expect(fetchMock).toHaveBeenCalledWith("/api/demo/reset", expect.objectContaining({ method: "POST" }));
    expect(screen.getByTestId("session-state")).toHaveTextContent('"triage":null');
    expect(screen.getByTestId("session-state")).toHaveTextContent('"noteDraft":""');
    expect(screen.getByTestId("session-state")).toHaveTextContent('"selectedProposalIds":[]');
    await user.click(screen.getByRole("button", { name: "Open provider chapter" }));
    expect(screen.getByTestId("session-state")).not.toHaveTextContent("Unsaved stale note");
  });
});

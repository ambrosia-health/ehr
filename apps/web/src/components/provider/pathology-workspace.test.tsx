import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PathologyWorkspace } from "@/components/provider/pathology-workspace";
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

describe("PathologyWorkspace", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("supports durable reviewed then notified stages without a dead end", async () => {
    const pathology = bootstrapFixture.pathology!;
    const originalStatus = pathology.status;
    const originalDraft = pathology.patientMessageDraft;
    const originalFollowup = pathology.followup;
    pathology.status = "received";
    pathology.followup = null;
    pathology.patientMessageDraft = {
      id: "draft-1",
      body: "Your pathology result is ready. Please review the monitoring plan.",
      status: "proposed",
      createdAt: "2026-07-21T08:43:00-04:00",
      aiProvenance: pathology.aiProvenance,
    };
    const fetchMock = vi.fn().mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      pathology.status = body.notifyPatient || pathology.status === "notified" ? "notified" : "reviewed";
      if (body.createFollowup) pathology.followup = { id: "followup-1", status: "open", title: "Offer six-month lesion follow-up", dueAt: "2026-08-04T09:00:00-04:00", completedAt: null };
      return new Response(JSON.stringify({
        resultId: pathology.id,
        status: pathology.status,
        reviewedAt: "2026-07-21T09:00:00-04:00",
        notificationId: body.notifyPatient ? "message-1" : null,
        closureTaskId: "closure-1",
        followupId: body.createFollowup ? "followup-1" : null,
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    try {
      const user = userEvent.setup();
      render(<AppProviders initialPersona="provider"><PathologyWorkspace /></AppProviders>);
      await user.click(screen.getByTestId("review-pathology"));
      await waitFor(() => expect(pathology.status).toBe("reviewed"));
      expect(screen.getByText("Reviewed · notification pending")).toBeVisible();
      expect(screen.getByTestId("review-pathology")).toBeDisabled();

      await user.click(screen.getByRole("checkbox", { name: /Approve patient communication/i }));
      await user.click(screen.getByTestId("review-pathology"));
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
      expect(await screen.findByText("Closure complete")).toBeVisible();
      expect(screen.getByText("Patient notified")).toBeVisible();

      const followup = screen.getByRole("checkbox", { name: /Create follow-up outreach/i });
      expect(followup).toBeEnabled();
      await user.click(followup);
      expect(screen.getByTestId("review-pathology")).toHaveTextContent("Create follow-up");
      await user.click(screen.getByTestId("review-pathology"));
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
      expect(followup).toBeDisabled();
      expect(screen.queryByTestId("review-pathology")).not.toBeInTheDocument();
    } finally {
      pathology.status = originalStatus;
      pathology.patientMessageDraft = originalDraft;
      pathology.followup = originalFollowup;
    }
  });

  it("never offers patient notification without the exact visible durable draft", () => {
    const pathology = bootstrapFixture.pathology!;
    const originalStatus = pathology.status;
    const originalDraft = pathology.patientMessageDraft;
    pathology.status = "received";
    pathology.patientMessageDraft = null;

    try {
      render(<AppProviders initialPersona="provider"><PathologyWorkspace /></AppProviders>);
      expect(screen.getByRole("checkbox", { name: /Patient communication unavailable/i })).toBeDisabled();
      expect(screen.getByTestId("pathology-message-draft")).toHaveTextContent(/notification is disabled/i);
      expect(screen.getByTestId("review-pathology")).toHaveTextContent("Record review");
    } finally {
      pathology.status = originalStatus;
      pathology.patientMessageDraft = originalDraft;
    }
  });

  it("keeps clinical coordinators in a read-only closure view", () => {
    const bootstrap = providerBootstrap as DemoBootstrap;
    const originalSession = bootstrap.session;
    const pathology = bootstrap.pathology!;
    const originalDraft = pathology.patientMessageDraft;
    bootstrap.session = { authenticated: true, persona: "clinical", presenter: false };
    pathology.patientMessageDraft = {
      id: "draft-1",
      body: "Your reviewed result is ready.",
      status: "proposed",
      createdAt: "2026-07-21T08:43:00-04:00",
      aiProvenance: pathology.aiProvenance,
    };
    try {
      render(<AppProviders initialPersona="clinical"><PathologyWorkspace /></AppProviders>);
      expect(screen.getByTestId("pathology-read-only")).toBeVisible();
      expect(screen.getByRole("checkbox", { name: /Approve patient communication/i })).toBeDisabled();
      expect(screen.getByTestId("pathology-followup")).toBeDisabled();
      expect(screen.getByTestId("review-pathology")).toBeDisabled();
    } finally {
      bootstrap.session = originalSession;
      pathology.patientMessageDraft = originalDraft;
    }
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CommandCenter } from "@/components/provider/command-center";
import type { ApiMode, DemoBootstrap } from "@/lib/api/types";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

let query = "";
let bootstrapResult: {
  data: DemoBootstrap | undefined;
  mode: ApiMode;
  error: Error | null;
  refetch: () => void;
};

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(query ? { q: query } : undefined),
}));

vi.mock("@/lib/api/hooks", () => ({
  useDemoBootstrap: () => bootstrapResult,
}));

function providerBootstrap(): DemoBootstrap {
  return {
    ...bootstrapFixture,
    session: { authenticated: true, persona: "provider", presenter: false },
    schedule: [{
      id: "appointment-1",
      time: "10:30",
      patient: "Sarah Mitchell",
      visit: "New lesion evaluation",
      provider: "Dr. Maya Chen",
      readiness: 100,
      readinessStatus: "ready",
      flags: ["AI summary"],
      status: "Arrived",
    }],
    queues: [
      { id: "path", label: "Pathology to review", count: 1, detail: "Final results awaiting clinician action", tone: "warning", href: "/pathology" },
      { id: "messages", label: "Patient messages", count: 1, detail: "Secure threads awaiting response", tone: "ai", href: "/messages" },
    ],
    conversations: [{
      id: "conversation-1",
      subject: "Shoulder biopsy and aftercare",
      patient: "Sarah Mitchell",
      unread: 1,
      risk: "routine",
      messages: [{ id: "message-1", sender: "Sarah Mitchell", sentAt: "2026-07-16T08:37:00-04:00", body: "Can I shower tomorrow morning?" }],
    }],
  };
}

describe("CommandCenter", () => {
  beforeEach(() => {
    query = "";
    bootstrapResult = {
      data: providerBootstrap(),
      mode: "live",
      error: null,
      refetch: vi.fn(),
    };
  });

  it("centers the workspace on the next patient and actionable queues", () => {
    render(<CommandCenter />);

    expect(screen.getByRole("heading", { name: "Sarah Mitchell", level: 1 })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open chart" })).toHaveAttribute("href", "/patients/sarah-mitchell");
    expect(screen.getByTestId("open-sarah-encounter")).toHaveAttribute("href", "/encounters/sarah-biopsy");
    expect(screen.getByRole("heading", { name: "Pathology results" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Messages" })).toBeVisible();
  });

  it("keeps the clinical context tabs interactive", async () => {
    const user = userEvent.setup();
    render(<CommandCenter />);

    await user.click(screen.getByRole("tab", { name: "History" }));

    expect(screen.getByRole("heading", { name: "Clinical history" })).toBeVisible();
    expect(screen.getByText("Adhesive tape")).toBeVisible();
  });

  it("uses the shell search query to filter the schedule rail", () => {
    query = "nobody";
    render(<CommandCenter />);

    expect(screen.getByText("No appointments match this search.")).toBeVisible();
    expect(screen.getByText("Filtered by “nobody”")).toBeVisible();
  });
});

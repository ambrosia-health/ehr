import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MessagingWorkspace } from "@/components/provider/messaging-workspace";
import { AppProviders } from "@/components/system/app-providers";
import type { DemoBootstrap } from "@/lib/api/types";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

const providerBootstrap = structuredClone({
  ...bootstrapFixture,
  session: { authenticated: true, persona: "provider", presenter: false },
  conversations: [
    {
      id: "conversation-taylor",
      subject: "Post-procedure question",
      patient: "Taylor Reed",
      unread: 0,
      risk: "routine",
      messages: [{ id: "message-taylor", sender: "Taylor Reed", sentAt: "2026-07-16T09:00:00-04:00", body: "Can I exercise tomorrow?" }],
    },
    {
      id: "conversation-sarah",
      subject: "Biopsy aftercare",
      patient: "Sarah Mitchell",
      unread: 2,
      risk: "routine",
      messages: [
        { id: "message-sarah", sender: "Sarah Mitchell", sentAt: "2026-07-16T09:05:00-04:00", body: "How should I care for the site?" },
        { id: "draft-sarah", sender: "Ambrosia draft", sentAt: "2026-07-16T09:06:00-04:00", body: "Keep the site covered with petrolatum and a clean bandage.", aiDraft: true },
      ],
    },
  ],
  queues: [{ id: "messages", label: "Messages", count: 2, detail: "Secure threads awaiting response", tone: "warning", href: "/messages" }],
} satisfies Partial<DemoBootstrap>) as DemoBootstrap;

vi.mock("@/lib/api/hooks", () => ({
  useDemoBootstrap: () => ({ data: providerBootstrap, mode: "live", error: null, refetch: vi.fn() }),
}));

describe("MessagingWorkspace", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("marks only a deliberately selected thread read and clears conversation-local draft state", async () => {
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/conversations/conversation-sarah/read") {
        providerBootstrap.conversations[1]!.unread = 0;
        providerBootstrap.queues[0]!.count = 0;
        return new Response(JSON.stringify({ conversationId: "conversation-sarah", changedCount: 2, readAt: "2026-07-16T09:10:00Z" }), { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(JSON.stringify({ detail: "Unexpected request" }), { status: 500, headers: { "content-type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppProviders initialPersona="provider"><MessagingWorkspace /></AppProviders>);

    expect(screen.getByTestId("messaging-unread-count")).toHaveTextContent("2 unread");
    await user.type(screen.getByLabelText("Reply to Taylor Reed"), "This draft belongs only to Taylor.");
    await user.click(screen.getByRole("button", { name: "Open conversation with Sarah Mitchell: Biopsy aftercare" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/conversations/conversation-sarah/read", expect.objectContaining({ method: "POST" })));
    expect(screen.getByTestId("messaging-unread-count")).toHaveTextContent("0 unread");
    expect(screen.queryByTestId("conversation-unread-conversation-sarah")).not.toBeInTheDocument();
    const sarahReply = screen.getByLabelText("Reply to Sarah Mitchell");
    expect(sarahReply).toHaveValue("Keep the site covered with petrolatum and a clean bandage.");
    expect((sarahReply as HTMLTextAreaElement).value).not.toContain("Taylor");
  });
});

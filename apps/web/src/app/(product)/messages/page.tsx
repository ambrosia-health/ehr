import type { Metadata } from "next";

import { InboxScreen } from "@/components/platform/inbox-screen";

export const metadata: Metadata = { title: "Inbox" };

export default function MessagesPage() {
  return <InboxScreen />;
}

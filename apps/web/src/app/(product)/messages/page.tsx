import type { Metadata } from "next";

import { MessagingWorkspace } from "@/components/provider/messaging-workspace";

export const metadata: Metadata = { title: "Secure messages" };

export default function MessagesPage() {
  return <MessagingWorkspace />;
}

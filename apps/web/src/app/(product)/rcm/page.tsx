import type { Metadata } from "next";

import { RevenueScreen } from "@/components/platform/revenue-screen";

export const metadata: Metadata = { title: "Revenue" };

export default function RcmPage() {
  return <RevenueScreen />;
}

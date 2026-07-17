import type { Metadata } from "next";

import { RcmWorkspace } from "@/components/rcm/rcm-workspace";

export const metadata: Metadata = { title: "Revenue cycle" };

export default function RcmPage() {
  return <RcmWorkspace />;
}

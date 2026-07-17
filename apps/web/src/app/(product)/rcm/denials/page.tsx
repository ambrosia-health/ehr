import type { Metadata } from "next";

import { DenialRecovery } from "@/components/rcm/rcm-workspace";

export const metadata: Metadata = { title: "Denial recovery" };

export default function DenialRecoveryPage() {
  return <DenialRecovery />;
}

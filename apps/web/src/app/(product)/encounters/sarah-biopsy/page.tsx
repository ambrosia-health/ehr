import type { Metadata } from "next";

import { EncounterWorkspace } from "@/components/provider/encounter-workspace";

export const metadata: Metadata = { title: "Sarah Mitchell encounter" };

export default function EncounterPage() {
  return <EncounterWorkspace />;
}

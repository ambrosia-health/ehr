import type { Metadata } from "next";

import { PatientAgentScreen } from "@/components/platform/patient-agent-screen";

export const metadata: Metadata = { title: "Sarah Mitchell" };

export default function SarahChartPage() {
  return <PatientAgentScreen />;
}

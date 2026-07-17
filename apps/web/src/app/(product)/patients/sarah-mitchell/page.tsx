import type { Metadata } from "next";

import { PatientChart } from "@/components/provider/patient-chart";

export const metadata: Metadata = { title: "Sarah Mitchell" };

export default function SarahChartPage() {
  return <PatientChart />;
}

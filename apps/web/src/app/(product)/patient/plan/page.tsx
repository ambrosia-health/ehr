import type { Metadata } from "next";

import { PatientPlanScreen } from "@/components/platform/patient-plan-screen";

export const metadata: Metadata = { title: "Your care plan" };

export default function PatientPlanPage() {
  return <PatientPlanScreen />;
}

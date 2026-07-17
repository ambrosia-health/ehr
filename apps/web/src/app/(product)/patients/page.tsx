import type { Metadata } from "next";

import { PatientsScreen } from "@/components/platform/patients-screen";

export const metadata: Metadata = { title: "Patients" };

export default function PatientsPage() {
  return <PatientsScreen />;
}

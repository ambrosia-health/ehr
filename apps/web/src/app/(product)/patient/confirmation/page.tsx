import type { Metadata } from "next";

import { PatientConfirmation } from "@/components/patient/patient-confirmation";

export const metadata: Metadata = { title: "Appointment confirmed" };

export default function ConfirmationPage() {
  return <PatientConfirmation />;
}

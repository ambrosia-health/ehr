import type { Metadata } from "next";

import { PatientIntake } from "@/components/patient/patient-intake";

export const metadata: Metadata = { title: "Start a dermatology visit" };

export default function PatientStartPage() {
  return <PatientIntake />;
}

import { PatientAgentScreen } from "@/components/platform/patient-agent-screen";

interface PatientPageProps {
  params: Promise<{ patientId: string }>;
}

export default async function PatientPage({ params }: PatientPageProps) {
  const { patientId } = await params;
  return <PatientAgentScreen patientId={patientId} />;
}

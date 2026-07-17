import type { Metadata } from "next";

import { MsoDashboard } from "@/components/mso/mso-dashboard";

export const metadata: Metadata = { title: "MSO intelligence" };

export default function MsoPage() {
  return <MsoDashboard />;
}

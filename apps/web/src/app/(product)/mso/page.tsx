import type { Metadata } from "next";

import { OperationsScreen } from "@/components/platform/operations-screen";

export const metadata: Metadata = { title: "Operations" };

export default function MsoPage() {
  return <OperationsScreen />;
}

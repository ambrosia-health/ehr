import type { Metadata } from "next";

import { ResultsScreen } from "@/components/platform/results-screen";

export const metadata: Metadata = { title: "Results" };

export default function PathologyPage() {
  return <ResultsScreen />;
}

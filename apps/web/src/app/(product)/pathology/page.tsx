import type { Metadata } from "next";

import { PathologyWorkspace } from "@/components/provider/pathology-workspace";

export const metadata: Metadata = { title: "Pathology" };

export default function PathologyPage() {
  return <PathologyWorkspace />;
}

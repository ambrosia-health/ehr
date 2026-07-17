import type { Metadata } from "next";

import { CommandCenter } from "@/components/provider/command-center";

export const metadata: Metadata = { title: "Command center" };

export default function CommandCenterPage() {
  return <CommandCenter />;
}

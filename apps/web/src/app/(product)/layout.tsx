import type { PropsWithChildren } from "react";

import { AppShell } from "@/components/shell/app-shell";

export default function ProductLayout({ children }: PropsWithChildren) {
  return <AppShell>{children}</AppShell>;
}

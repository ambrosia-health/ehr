import type { PropsWithChildren } from "react";

import { ProductWorkspaceProvider } from "@/components/platform/product-workspace-provider";
import { AppShell } from "@/components/shell/app-shell";

export default function ProductLayout({ children }: PropsWithChildren) {
  return (
    <ProductWorkspaceProvider>
      <AppShell>{children}</AppShell>
    </ProductWorkspaceProvider>
  );
}

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { PropsWithChildren } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { hasDemoSessionCookie } from "@/lib/auth/session-lifecycle";

export default async function ProductLayout({ children }: PropsWithChildren) {
  if (!hasDemoSessionCookie(await cookies())) redirect("/login");

  return <AppShell>{children}</AppShell>;
}

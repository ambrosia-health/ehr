import { ArrowLeft, HeartPulse } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return <main className="flex min-h-screen items-center justify-center bg-muted/20 p-6"><div className="max-w-md text-center"><span className="mx-auto flex size-11 items-center justify-center rounded-lg bg-primary text-primary-foreground"><HeartPulse className="size-5" /></span><p className="mt-6 font-mono text-xs text-muted-foreground">404</p><h1 className="mt-2 text-2xl font-semibold tracking-[-0.04em]">This workspace does not exist.</h1><p className="mt-2 text-sm text-muted-foreground">Return to the command center and continue the synthetic demo journey.</p><Button asChild className="mt-6"><Link href="/command-center"><ArrowLeft className="size-4" /> Command center</Link></Button></div></main>;
}

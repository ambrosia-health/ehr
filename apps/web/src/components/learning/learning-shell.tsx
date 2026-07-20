import { Database, FlaskConical, ShieldCheck } from "lucide-react";
import type { PropsWithChildren } from "react";

export function LearningShell({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex min-h-16 max-w-[100rem] items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <span className="flex size-9 items-center justify-center rounded-lg bg-foreground text-background">
            <FlaskConical className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-semibold tracking-[-0.02em]">Ambrosia Learning</span>
              <span className="rounded border border-border bg-muted px-1.5 py-0.5 text-[9px] font-bold tracking-[0.16em] text-muted-foreground">
                INTERNAL
              </span>
            </div>
            <p className="text-xs text-muted-foreground">Trajectory and evaluation evidence</p>
          </div>
          <div className="ml-auto hidden items-center gap-4 text-xs text-muted-foreground sm:flex">
            <span className="flex items-center gap-1.5">
              <Database className="size-3.5" aria-hidden="true" />
              Governed records
            </span>
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="size-3.5 text-evidence" aria-hidden="true" />
              Synthetic runs only
            </span>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[100rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
    </div>
  );
}

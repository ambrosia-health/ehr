"use client";

import { AlertCircle, LoaderCircle, RotateCcw } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function PageLoading({ label = "Loading workspace" }: { label?: string }) {
  return (
    <div className="space-y-5" role="status" aria-label={label}>
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" />
        {label}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {["a", "b", "c"].map((key) => (
          <div key={key} className="space-y-3 rounded-xl border bg-card p-5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-36" />
            <Skeleton className="h-3 w-full" />
          </div>
        ))}
      </div>
      <Skeleton className="h-80 w-full rounded-xl" />
    </div>
  );
}

export function PageError({ error, retry }: { error: Error | null; retry: () => void }) {
  return (
    <div className="mx-auto mt-14 max-w-xl space-y-5 rounded-xl border border-destructive/30 bg-card p-8 text-center">
      <span className="mx-auto flex size-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertCircle className="size-5" />
      </span>
      <div>
        <h2 className="text-lg font-semibold">We could not open this workspace</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {error?.message ?? "Your session may have expired. Try the request again."}
        </p>
      </div>
      <div className="flex justify-center gap-2"><Button onClick={retry}><RotateCcw className="size-4" /> Retry</Button><Button asChild variant="outline"><Link href="/">Open Today</Link></Button></div>
    </div>
  );
}

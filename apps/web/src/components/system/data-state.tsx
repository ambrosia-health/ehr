"use client";

import { AlertCircle, LoaderCircle, LockKeyhole, RotateCcw } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
          <Card key={key}>
            <CardContent className="space-y-3 p-5">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-9 w-36" />
              <Skeleton className="h-3 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Skeleton className="h-80 w-full rounded-xl" />
    </div>
  );
}

export function PageError({ error, retry }: { error: Error | null; retry: () => void }) {
  return (
    <Card className="mx-auto mt-14 max-w-xl border-destructive/30">
      <CardContent className="space-y-5 p-8 text-center">
        <span className="mx-auto flex size-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <AlertCircle className="size-5" />
        </span>
        <div>
          <h2 className="text-lg font-semibold">We could not open this workspace</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {error?.message ?? "Your session may have expired. Try the request again."}
          </p>
        </div>
        <div className="flex justify-center gap-2"><Button onClick={retry}><RotateCcw className="size-4" /> Retry</Button><Button asChild variant="outline"><Link href="/login">Return to sign in</Link></Button></div>
      </CardContent>
    </Card>
  );
}

export function WorkspaceUnavailable({
  title = "This workspace is not available for your role",
  description = "Ambrosia only returns the records and operational domains authorized for the active session.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <Card className="mx-auto mt-14 max-w-xl">
      <CardContent className="space-y-5 p-8 text-center">
        <span className="mx-auto flex size-11 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <LockKeyhole className="size-5" />
        </span>
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        <Button asChild variant="outline"><Link href="/login">Switch persona</Link></Button>
      </CardContent>
    </Card>
  );
}

"use client";

import { KeyRound, LockKeyhole } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiRequest } from "@/lib/api/client";

interface AccessGateProps {
  onAuthenticated: () => Promise<void>;
}

export function AccessGate({ onAuthenticated }: AccessGateProps) {
  const [presenterCode, setPresenterCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/api/auth/demo/session", {
        method: "POST",
        body: { persona: "owner", presenterCode },
      });
      setPresenterCode("");
      await onAuthenticated();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Access could not be verified.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto mt-8 max-w-md rounded-xl border border-border bg-card p-6 shadow-sm sm:mt-16 sm:p-8" aria-labelledby="access-title">
      <span className="flex size-11 items-center justify-center rounded-lg bg-secondary text-primary">
        <LockKeyhole className="size-5" aria-hidden="true" />
      </span>
      <h1 id="access-title" className="mt-5 text-xl font-semibold tracking-[-0.025em]">
        Learning Console access
      </h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Enter the presenter code to inspect synthetic trajectories and evaluation runs. Access is audited and scoped to this demo tenant.
      </p>
      <form className="mt-6 space-y-4" onSubmit={submit}>
        <div className="space-y-1.5">
          <label htmlFor="presenter-code" className="text-sm font-medium">
            Presenter code
          </label>
          <Input
            id="presenter-code"
            type="password"
            autoComplete="one-time-code"
            value={presenterCode}
            onChange={(event) => setPresenterCode(event.target.value)}
            required
            className="h-10"
          />
        </div>
        {error ? (
          <p role="alert" className="rounded-md bg-safety-muted px-3 py-2 text-sm text-safety">
            {error}
          </p>
        ) : null}
        <Button type="submit" size="lg" className="w-full" disabled={submitting || presenterCode.length === 0}>
          <KeyRound className="size-4" aria-hidden="true" />
          {submitting ? "Verifying…" : "Open console"}
        </Button>
      </form>
    </section>
  );
}

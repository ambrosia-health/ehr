"use client";

import { CircleAlert, Clock3, LoaderCircle, Play, Plus, RotateCcw, StepForward } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { formatDate, formatLabel, formatModel, formatReward } from "@/components/learning/format";
import { normalizeEnvironmentRunView, normalizeRunHistory } from "@/components/learning/normalize";
import { RunStepCard } from "@/components/learning/run-step-card";
import { StatusBadge } from "@/components/learning/status-badge";
import type { EpisodeDefinition, RunHistory, RunSummary } from "@/components/learning/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiRequest } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface RunsPanelProps {
  episodeDefinitions: EpisodeDefinition[];
  runs: RunSummary[];
  onRefresh: () => Promise<void>;
}

async function requestRunHistory(runId: string, signal?: AbortSignal, afterStep = 0): Promise<RunHistory> {
  const cursor = afterStep > 0 ? `?after_step=${afterStep}&limit=50` : "";
  const response = await apiRequest<unknown>(`/api/demo/learning/environment-runs/${runId}/history${cursor}`, { signal });
  return normalizeRunHistory(response);
}

function idempotencyKey(prefix: string): string {
  return `${prefix}-${globalThis.crypto.randomUUID()}`;
}

export function RunsPanel({ episodeDefinitions, runs, onRefresh }: RunsPanelProps) {
  const [selectedId, setSelectedId] = useState<string | null>(runs[0]?.id ?? null);
  const [history, setHistory] = useState<RunHistory | null>(null);
  const [definitionId, setDefinitionId] = useState(episodeDefinitions[0]?.id ?? "");
  const [seed, setSeed] = useState("17");
  const [loadingHistory, setLoadingHistory] = useState(runs.length > 0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [busy, setBusy] = useState<"create" | "step" | "complete" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const modelRequest = useRef<AbortController | null>(null);

  const loadHistory = useCallback(async (runId: string, signal?: AbortSignal) => {
    try {
      setHistory(await requestRunHistory(runId, signal));
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 0 && signal?.aborted) return;
      setError(caught instanceof Error ? caught.message : "Run history could not be loaded.");
    } finally {
      if (!signal?.aborted) setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    void requestRunHistory(selectedId, controller.signal)
      .then(setHistory)
      .catch((caught: unknown) => {
        if (caught instanceof ApiError && caught.status === 0 && controller.signal.aborted) return;
        setError(caught instanceof Error ? caught.message : "Run history could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingHistory(false);
      });
    return () => controller.abort();
  }, [selectedId]);

  useEffect(() => () => modelRequest.current?.abort(), []);

  async function loadMoreHistory() {
    if (!selectedId || history?.run.id !== selectedId || history.nextAfterStep === null || loadingMore) return;
    setLoadingMore(true);
    setError(null);
    try {
      const next = await requestRunHistory(selectedId, undefined, history.nextAfterStep);
      setHistory((current) => current?.run.id === selectedId
        ? { ...next, steps: [...current.steps, ...next.steps] }
        : current);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "More run steps could not be loaded.");
    } finally {
      setLoadingMore(false);
    }
  }

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedSeed = Number(seed);
    if (!Number.isInteger(parsedSeed) || parsedSeed < 0) {
      setError("Seed must be a non-negative whole number.");
      return;
    }
    setBusy("create");
    setError(null);
    setNotice(null);
    try {
      const rawResponse = await apiRequest<unknown>("/api/demo/learning/environment-runs", {
        method: "POST",
        body: {
          episodeDefinitionId: definitionId,
          actorRole: "environment_agent",
          seed: parsedSeed,
          idempotencyKey: idempotencyKey("console-run"),
        },
      });
      const response = normalizeEnvironmentRunView(rawResponse);
      await onRefresh();
      setSelectedId(response.run.id);
      setNotice("Synthetic environment run created.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The environment run could not be created.");
    } finally {
      setBusy(null);
    }
  }

  async function runModel(complete: boolean) {
    if (!selectedId) return;
    const selectedRun = history?.run.id === selectedId ? history.run : runs.find((run) => run.id === selectedId);
    if (!selectedRun || selectedRun.status !== "running") return;
    setBusy(complete ? "complete" : "step");
    setError(null);
    setNotice(null);
    const controller = new AbortController();
    modelRequest.current = controller;
    try {
      let sequence = selectedRun.sequence;
      let status = selectedRun.status;
      const maxSteps = selectedRun.maxSteps ?? 100;
      const stepLimit = complete ? Math.min(Math.max(maxSteps, 1), 100) : 1;
      for (let attempt = 0; attempt < stepLimit && status === "running"; attempt += 1) {
        const rawResponse = await apiRequest<unknown>(`/api/demo/learning/environment-runs/${selectedId}/model-step`, {
          method: "POST",
          signal: controller.signal,
          body: {
            expectedSequence: sequence + 1,
            idempotencyKey: idempotencyKey("console-model-step"),
          },
        });
        const response = normalizeEnvironmentRunView(rawResponse);
        sequence = response.run.sequence;
        status = response.run.status;
      }
      if (complete && status === "running") throw new Error(`Run remained active after the ${stepLimit}-step console safety limit.`);
      await Promise.all([loadHistory(selectedId), onRefresh()]);
      setNotice(complete ? "Model run reached a terminal state." : "One model step completed.");
    } catch (caught) {
      if (controller.signal.aborted) return;
      setError(caught instanceof Error ? caught.message : "The model step could not be completed.");
      await Promise.allSettled([loadHistory(selectedId), onRefresh()]);
    } finally {
      if (modelRequest.current === controller) modelRequest.current = null;
      setBusy(null);
    }
  }

  const selectedRun = history?.run.id === selectedId ? history.run : runs.find((run) => run.id === selectedId) ?? null;
  const runIsActive = selectedRun?.status === "running";

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-border bg-card p-4 sm:p-5" aria-labelledby="new-run-title">
        <div className="flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-secondary text-primary"><Plus className="size-4" aria-hidden="true" /></span>
          <div>
            <h2 id="new-run-title" className="font-semibold">New synthetic run</h2>
            <p className="mt-1 text-sm text-muted-foreground">Create an isolated environment from a released episode definition.</p>
          </div>
        </div>
        <form className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_9rem_auto] md:items-end" onSubmit={createRun}>
          <div className="space-y-1.5">
            <label htmlFor="episode-definition" className="text-xs font-medium">Episode definition</label>
            <select
              id="episode-definition"
              value={definitionId}
              onChange={(event) => setDefinitionId(event.target.value)}
              disabled={episodeDefinitions.length === 0 || busy !== null}
              className="h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {episodeDefinitions.map((definition) => <option key={definition.id} value={definition.id}>{definition.name} · v{definition.version}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="run-seed" className="text-xs font-medium">Seed</label>
            <Input id="run-seed" type="number" min="0" step="1" value={seed} onChange={(event) => setSeed(event.target.value)} disabled={busy !== null} className="h-9 font-mono" />
          </div>
          <Button type="submit" size="lg" disabled={!definitionId || busy !== null}>
            {busy === "create" ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Plus className="size-4" aria-hidden="true" />}
            Create run
          </Button>
        </form>
      </section>

      {error ? <p role="alert" className="flex items-start gap-2 rounded-md border border-safety/25 bg-safety-muted px-3 py-2 text-sm text-safety"><CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />{error}</p> : null}
      {notice ? <p role="status" className="rounded-md border border-evidence/20 bg-evidence-muted px-3 py-2 text-sm text-evidence-foreground">{notice}</p> : null}

      <div className="grid gap-5 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <aside aria-label="Environment runs">
          <div className="mb-3 flex items-end justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold">Environment runs</h2>
              <p className="mt-1 text-sm text-muted-foreground">Newest captured runs.</p>
            </div>
            <Button type="button" variant="ghost" size="icon-sm" aria-label="Refresh runs" onClick={() => void onRefresh()}><RotateCcw className="size-3.5" /></Button>
          </div>
          {runs.length ? (
            <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
              {runs.map((run) => (
                <li key={run.id}>
                  <button
                    type="button"
                    aria-pressed={run.id === selectedId}
                    disabled={busy !== null}
                    onClick={() => {
                      if (run.id === selectedId) return;
                      setLoadingHistory(true);
                      setError(null);
                      setSelectedId(run.id);
                    }}
                    className={cn("w-full rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", run.id === selectedId ? "border-primary bg-secondary" : "border-border bg-card hover:bg-muted/60")}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold">Run {run.id.slice(0, 8)}</span>
                      <StatusBadge label={formatLabel(run.status)} tone={run.status === "completed" ? "good" : run.status === "running" ? "evidence" : "warning"} />
                    </span>
                    <span className="mt-2 block truncate text-xs text-muted-foreground">{formatModel(run.model)}</span>
                    <span className="mt-2 flex items-center justify-between text-xs text-muted-foreground"><span>Seed {run.seed} · Step {run.sequence}</span><span>{run.fallbackUsed === true ? "Fallback" : `${run.hardViolationCount} violations`}</span></span>
                  </button>
                </li>
              ))}
            </ul>
          ) : <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">No environment runs yet.</p>}
        </aside>

        <section aria-live="polite" aria-busy={loadingHistory}>
          {!selectedId ? (
            <p className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">Create or select a run to inspect its model steps.</p>
          ) : loadingHistory ? (
            <p role="status" className="flex items-center gap-2 rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" aria-hidden="true" />Loading complete run history…</p>
          ) : history?.run.id === selectedId ? (
            <div>
              <div className="rounded-lg border border-border bg-card p-4 sm:p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs text-muted-foreground">{history.run.id}</p>
                    <h3 className="mt-1 text-lg font-semibold">{formatModel(history.run.model)}</h3>
                    <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground"><Clock3 className="size-3" aria-hidden="true" />Started {formatDate(history.run.startedAt)}</p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <StatusBadge label={formatLabel(history.run.status)} tone={history.run.status === "completed" ? "good" : "evidence"} />
                    {history.run.fallbackUsed === true ? <StatusBadge label="Fallback used" tone="warning" /> : null}
                    {history.run.fallbackUsed === false ? <StatusBadge label="Direct model" tone="good" /> : null}
                    {history.run.hardViolationCount ? <StatusBadge label={`${history.run.hardViolationCount} hard violations`} tone="danger" /> : null}
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4">
                  <Button type="button" onClick={() => void runModel(false)} disabled={!runIsActive || busy !== null}>
                    {busy === "step" ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <StepForward className="size-4" aria-hidden="true" />}
                    Run model step
                  </Button>
                  <Button type="button" variant="outline" onClick={() => void runModel(true)} disabled={!runIsActive || busy !== null}>
                    {busy === "complete" ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
                    Run to completion
                  </Button>
                  {!runIsActive ? <span className="self-center text-xs text-muted-foreground">This run is terminal.</span> : null}
                </div>
                {Object.keys(history.run.totalReward).length ? (
                  <dl className="mt-4 grid gap-2 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4">
                    {Object.entries(history.run.totalReward).map(([name, value]) => <div key={name}><dt className="text-[11px] text-muted-foreground">{formatLabel(name)}</dt><dd className="mt-0.5 font-mono text-sm font-semibold">{formatReward(value)}</dd></div>)}
                  </dl>
                ) : null}
              </div>
              {history.steps.length ? (
                <div>
                  <ol className="mt-4 space-y-3">{history.steps.map((step) => <RunStepCard key={step.sequence} step={step} />)}</ol>
                  {history.nextAfterStep !== null ? (
                    <Button type="button" variant="outline" className="mt-4 w-full" disabled={loadingMore} onClick={() => void loadMoreHistory()}>
                      {loadingMore ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}
                      Load more steps
                    </Button>
                  ) : null}
                </div>
              ) : <p className="mt-4 rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">This run is ready for its first model step.</p>}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

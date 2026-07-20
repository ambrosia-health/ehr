"use client";

import { Bot, CheckCircle2, CircleAlert, GitBranch, LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { formatLabel } from "@/components/learning/format";
import { normalizeEpisodeTrajectory } from "@/components/learning/normalize";
import { StatusBadge } from "@/components/learning/status-badge";
import { TrajectoryStepCard } from "@/components/learning/trajectory-step-card";
import type { EpisodeSummary, EpisodeTrajectory } from "@/components/learning/types";
import { Button } from "@/components/ui/button";
import { ApiError, apiRequest } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface TrajectoriesPanelProps {
  episodes: EpisodeSummary[];
}

async function requestTrajectory(episodeId: string, signal?: AbortSignal, offset = 0): Promise<EpisodeTrajectory> {
  const cursor = offset > 0 ? `?offset=${offset}&limit=50` : "";
  const response = await apiRequest<unknown>(`/api/demo/learning/episodes/${episodeId}/trajectory${cursor}`, { signal });
  return normalizeEpisodeTrajectory(response);
}

export function TrajectoriesPanel({ episodes }: TrajectoriesPanelProps) {
  const [selectedId, setSelectedId] = useState<string | null>(episodes[0]?.id ?? null);
  const [trajectory, setTrajectory] = useState<EpisodeTrajectory | null>(null);
  const [loading, setLoading] = useState(episodes.length > 0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTrajectory = useCallback(async (episodeId: string, signal?: AbortSignal) => {
    try {
      setTrajectory(await requestTrajectory(episodeId, signal));
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 0 && signal?.aborted) return;
      setError(caught instanceof Error ? caught.message : "The trajectory could not be loaded.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    void requestTrajectory(selectedId, controller.signal)
      .then(setTrajectory)
      .catch((caught: unknown) => {
        if (caught instanceof ApiError && caught.status === 0 && controller.signal.aborted) return;
        setError(caught instanceof Error ? caught.message : "The trajectory could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [selectedId]);

  async function loadMore() {
    const nextOffset = trajectory?.nextOffset;
    if (!selectedId || nextOffset === null || nextOffset === undefined || loadingMore) return;
    setLoadingMore(true);
    setError(null);
    try {
      const next = await requestTrajectory(selectedId, undefined, nextOffset);
      setTrajectory((current) => current?.episode.id === selectedId
        ? {
            ...current,
            steps: [...current.steps, ...next.steps],
            nextOffset: next.nextOffset,
            evidenceTruncated: current.evidenceTruncated || next.evidenceTruncated,
          }
        : current);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "More trajectory decisions could not be loaded.");
    } finally {
      setLoadingMore(false);
    }
  }

  if (episodes.length === 0) {
    return <p className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">No captured episodes are available.</p>;
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[19rem_minmax(0,1fr)]">
      <aside aria-label="Captured episodes" className="xl:sticky xl:top-5 xl:self-start">
        <div className="mb-3">
          <h2 className="text-base font-semibold">Trajectories</h2>
          <p className="mt-1 text-sm text-muted-foreground">Select an episode to reconstruct its decisions.</p>
        </div>
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
          {episodes.map((episode) => {
            const selected = episode.id === selectedId;
            return (
              <li key={episode.id}>
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => {
                    if (selected) return;
                    setLoading(true);
                    setError(null);
                    setSelectedId(episode.id);
                  }}
                  className={cn(
                    "w-full rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selected ? "border-primary bg-secondary" : "border-border bg-card hover:bg-muted/60",
                  )}
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className="line-clamp-2 text-sm font-semibold">{episode.episodeKey}</span>
                    {episode.sourceKind === "simulation" || episode.sourceKind === "synthetic" ? <Bot className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden="true" /> : <GitBranch className="mt-0.5 size-3.5 shrink-0 text-evidence" aria-hidden="true" />}
                  </span>
                  <span className="mt-2 flex flex-wrap gap-1.5">
                    <StatusBadge label={formatLabel(episode.sourceKind)} tone="evidence" />
                    <StatusBadge label={formatLabel(episode.status)} tone={episode.status === "completed" ? "good" : "neutral"} />
                  </span>
                  {episode.decisionCount !== null || episode.outcomeCount !== null ? (
                    <span className="mt-2 block text-xs text-muted-foreground">{episode.decisionCount ?? "—"} decisions · {episode.outcomeCount ?? "—"} outcomes</span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      </aside>

      <section aria-live="polite" aria-busy={loading}>
        {loading ? (
          <p role="status" className="flex items-center gap-2 rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" aria-hidden="true" />Loading decision timeline…</p>
        ) : error ? (
          <div className="rounded-lg border border-safety/25 bg-card p-5">
            <p role="alert" className="flex items-center gap-2 text-sm text-safety"><CircleAlert className="size-4" aria-hidden="true" />{error}</p>
            {selectedId ? <Button className="mt-4" variant="outline" onClick={() => { setLoading(true); setError(null); void loadTrajectory(selectedId); }}>Try again</Button> : null}
          </div>
        ) : trajectory ? (
          <div>
            <div className="mb-4 rounded-lg border border-border bg-card px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs text-muted-foreground">{trajectory.episode.definition}</p>
                  <h2 className="mt-1 font-semibold">{trajectory.episode.episodeKey}</h2>
                </div>
                <span className="flex items-center gap-1.5 text-xs text-evidence-foreground"><CheckCircle2 className="size-3.5" aria-hidden="true" />Point-in-time evidence</span>
              </div>
            </div>
            {trajectory.steps.length ? (
              <div>
                <ol className="space-y-4">
                  {trajectory.steps.map((step) => <li key={step.sequence}><TrajectoryStepCard step={step} /></li>)}
                </ol>
                {trajectory.nextOffset !== null ? (
                  <Button type="button" variant="outline" className="mt-4 w-full" disabled={loadingMore} onClick={() => void loadMore()}>
                    {loadingMore ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}
                    Load more decisions
                  </Button>
                ) : null}
                {trajectory.evidenceTruncated ? (
                  <p role="status" className="mt-4 rounded-md border border-safety/25 bg-safety-muted px-3 py-2 text-sm text-safety">
                    This inspection view reached its bounded evidence limit. The captured dataset retains the full governed record.
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">This episode has no captured decisions.</p>
            )}
          </div>
        ) : null}
      </section>
    </div>
  );
}

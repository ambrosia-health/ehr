import { Activity, Bot, CircleAlert, GitBranch, ListChecks, Waypoints } from "lucide-react";

import { formatDate, formatLabel } from "@/components/learning/format";
import { StatusBadge } from "@/components/learning/status-badge";
import type { AiRunSummary, LearningOverview } from "@/components/learning/types";

interface OverviewPanelProps {
  overview: LearningOverview;
  aiRuns: AiRunSummary[];
}

const metrics = [
  { key: "episodeCount", label: "Episodes", icon: GitBranch },
  { key: "activeEpisodeCount", label: "Active episodes", icon: Activity },
  { key: "environmentRunCount", label: "Environment runs", icon: Bot },
  { key: "activeEnvironmentRunCount", label: "Active runs", icon: Waypoints },
  { key: "datasetReleaseCount", label: "Dataset releases", icon: ListChecks },
  { key: "hardViolationCount", label: "Hard violations", icon: CircleAlert },
] as const;

export function OverviewPanel({ overview, aiRuns }: OverviewPanelProps) {
  return (
    <div className="space-y-6">
      <section aria-labelledby="capture-overview-title">
        <div className="mb-3 flex items-end justify-between gap-4">
          <div>
            <h2 id="capture-overview-title" className="text-base font-semibold">Capture overview</h2>
            <p className="mt-1 text-sm text-muted-foreground">Current evidence in the governed learning substrate.</p>
          </div>
          <StatusBadge label={`${overview.aiRunCount} AI runs · ${overview.failedAiRunCount} failed`} tone={overview.failedAiRunCount ? "warning" : "evidence"} />
        </div>
        <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {metrics.map(({ key, label, icon: Icon }) => {
            const value = overview[key];
            const violation = key === "hardViolationCount" && value > 0;
            return (
              <div key={key} className="rounded-lg border border-border bg-card p-4">
                <dt className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <Icon className={violation ? "size-4 text-safety" : "size-4 text-primary"} aria-hidden="true" />
                  {label}
                </dt>
                <dd className={violation ? "mt-3 font-mono text-2xl font-semibold text-safety" : "mt-3 font-mono text-2xl font-semibold"}>
                  {value.toLocaleString()}
                </dd>
              </div>
            );
          })}
        </dl>
      </section>

      <section className="rounded-lg border border-border bg-card" aria-labelledby="recent-ai-title">
        <div className="border-b border-border px-4 py-3 sm:px-5">
          <h2 id="recent-ai-title" className="text-sm font-semibold">Recent AI provenance</h2>
          <p className="mt-1 text-xs text-muted-foreground">Provider calls and deterministic fallbacks captured by the EHR.</p>
        </div>
        {aiRuns.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-muted-foreground">No AI runs have been captured yet.</p>
        ) : (
          <ul className="divide-y divide-border">
            {aiRuns.slice(0, 8).map((run) => (
              <li key={run.id} className="grid gap-3 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium">{formatLabel(run.capability)}</p>
                    <StatusBadge label={formatLabel(run.status)} tone={["completed", "succeeded"].includes(run.status) ? "good" : "warning"} />
                    {run.fallbackUsed ? <StatusBadge label="Fallback" tone="warning" /> : null}
                  </div>
                  <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{run.provider} / {run.model}</p>
                </div>
                <div className="text-left text-xs text-muted-foreground sm:text-right">
                  <p>{run.latencyMs === null ? "Latency unavailable" : `${run.latencyMs} ms`}</p>
                  <p className="mt-1">{formatDate(run.startedAt)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

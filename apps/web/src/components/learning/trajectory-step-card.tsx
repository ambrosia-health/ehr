import { Clock3, FileKey2 } from "lucide-react";

import { formatDate, formatLabel, formatValue } from "@/components/learning/format";
import { StatusBadge } from "@/components/learning/status-badge";
import type { TrajectoryStep } from "@/components/learning/types";

interface TrajectoryStepCardProps {
  step: TrajectoryStep;
}

export function TrajectoryStepCard({ step }: TrajectoryStepCardProps) {
  const snapshotEntries = Object.entries(step.observation.syntheticSnapshot ?? {});

  return (
    <article className="relative rounded-lg border border-border bg-card p-4 sm:p-5" aria-labelledby={`decision-${step.sequence}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] font-semibold text-primary">DECISION {step.sequence}</p>
          <h3 id={`decision-${step.sequence}`} className="mt-1 font-semibold">{formatLabel(step.decisionType)}</h3>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground"><Clock3 className="size-3" aria-hidden="true" />Opened {formatDate(step.openedAt)}</p>
        </div>
        {step.action ? (
          <StatusBadge label={formatLabel(step.action.status)} tone={step.action.status === "succeeded" ? "good" : "warning"} />
        ) : (
          <StatusBadge label="No action" tone="warning" />
        )}
      </div>

      <section className="mt-5 rounded-md border border-evidence/20 bg-evidence-muted/45 p-4" aria-label={`Observation for decision ${step.sequence}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-xs font-semibold uppercase tracking-[0.08em] text-evidence-foreground">Observation at cutoff</h4>
          <span className="text-xs text-muted-foreground">{formatDate(step.observation.asOfAt)}</span>
        </div>
        <p className="mt-3 text-[11px] text-muted-foreground">Manifest hash</p>
        <code className="mt-1 block break-all font-mono text-[11px] text-foreground">{step.observation.manifestHash}</code>
        {snapshotEntries.length ? (
          <dl className="mt-4 grid gap-x-5 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
            {snapshotEntries.map(([key, value]) => (
              <div key={key}>
                <dt className="text-[11px] font-medium text-muted-foreground">{formatLabel(key)}</dt>
                <dd className="mt-0.5 text-sm">{formatValue(value)}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {step.observation.resources.length ? (
          <div className="mt-4 border-t border-evidence/15 pt-3">
            <p className="text-[11px] font-medium text-muted-foreground">Referenced resources</p>
            <ul className="mt-2 space-y-2">
              {step.observation.resources.map((resource, index) => (
                <li key={`${resource.resourceType ?? "resource"}-${resource.resourceIdentityHash ?? index}`} className="grid gap-1 text-xs sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
                  <span className="font-medium">{formatLabel(resource.resourceType ?? "Resource")} {resource.resourceVersion === undefined ? "" : `v${resource.resourceVersion}`}</span>
                  <code className="break-all font-mono text-[10px] text-muted-foreground">{resource.contentHash ?? resource.resourceIdentityHash ?? "Reference withheld"}</code>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <section aria-label={`Available actions for decision ${step.sequence}`}>
          <h4 className="text-xs font-semibold text-muted-foreground">Available actions</h4>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {step.availableActions.map((action) => (
              <span key={action} className="rounded border border-border bg-muted px-2 py-1 font-mono text-[11px]">{action}</span>
            ))}
          </div>
        </section>
        <section aria-label={`Selected action for decision ${step.sequence}`}>
          <h4 className="text-xs font-semibold text-muted-foreground">Selected action</h4>
          {step.action ? (
            <div className="mt-2 rounded-md border border-decision/20 bg-decision-muted px-3 py-2 text-sm">
              <p className="font-semibold text-decision">{formatLabel(step.action.type)}</p>
              <p className="mt-1 text-xs text-muted-foreground">{formatLabel(step.action.actorKind)} actor{step.action.aiRunId ? ` · AI run ${step.action.aiRunId}` : ""}</p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">No action was recorded.</p>
          )}
        </section>
      </div>

      <section className="mt-4 border-t border-border pt-4" aria-label={`Outcomes for decision ${step.sequence}`}>
        <h4 className="text-xs font-semibold text-muted-foreground">Outcomes</h4>
        {step.outcomes.length ? (
          <ul className="mt-2 grid gap-2 xl:grid-cols-2">
            {step.outcomes.map((outcome, index) => (
              <li key={`${outcome.type}-${outcome.observedAt}-${index}`} className="rounded-md border border-border px-3 py-2 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{formatLabel(outcome.type)}</span>
                  <StatusBadge label={formatLabel(outcome.provenanceKind)} tone={outcome.provenanceKind === "observed" ? "good" : "neutral"} />
                </div>
                <p className="mt-1 text-muted-foreground">{formatValue(outcome.value)}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">No outcome has matured for this decision.</p>
        )}
      </section>

      {step.event ? (
        <footer className="mt-4 flex flex-wrap items-start gap-x-3 gap-y-1 border-t border-border pt-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1 font-medium text-foreground"><FileKey2 className="size-3" aria-hidden="true" />{formatLabel(step.event.type)}</span>
          <code className="min-w-0 break-all font-mono">{step.event.payloadHash}</code>
        </footer>
      ) : null}
    </article>
  );
}

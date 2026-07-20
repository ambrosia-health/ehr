import { Bot, ShieldAlert } from "lucide-react";

import { formatLabel, formatReward } from "@/components/learning/format";
import { StatusBadge } from "@/components/learning/status-badge";
import type { RunHistoryStep } from "@/components/learning/types";
import { cn } from "@/lib/utils";

interface RunStepCardProps {
  step: RunHistoryStep;
}

export function RunStepCard({ step }: RunStepCardProps) {
  const rewards = Object.entries(step.reward);

  return (
    <li className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] font-semibold text-primary">STEP {step.sequence}</p>
          <h4 className="mt-1 font-semibold">{formatLabel(step.actionType)}</h4>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <StatusBadge label={formatLabel(step.actionStatus)} tone={step.actionStatus === "succeeded" ? "good" : "warning"} />
          <StatusBadge label={formatLabel(step.supportKind)} tone={step.supportKind === "observed" ? "good" : "neutral"} />
        </div>
      </div>
      {step.model ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md bg-muted px-3 py-2 text-xs">
          <Bot className="size-3.5 text-primary" aria-hidden="true" />
          <span className="font-mono">{step.model.provider} / {step.model.model}</span>
          {step.model.fallbackUsed ? <StatusBadge label="Fallback used" tone="warning" /> : <StatusBadge label="Direct model" tone="good" />}
          <span className="text-muted-foreground">{step.model.latencyMs === null ? "Latency unavailable" : `${step.model.latencyMs} ms`}</span>
        </div>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">No model provenance was linked to this step.</p>
      )}
      <div className="mt-4">
        <p className="text-xs font-semibold text-muted-foreground">Vector reward</p>
        {rewards.length ? (
          <dl className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {rewards.map(([name, value]) => (
              <div key={name} className="flex items-center justify-between gap-3 rounded border border-border px-2.5 py-2 text-xs">
                <dt>{formatLabel(name)}</dt>
                <dd className={cn("font-mono font-semibold", value < 0 ? "text-safety" : "text-evidence-foreground")}>{formatReward(value)}</dd>
              </div>
            ))}
          </dl>
        ) : <p className="mt-2 text-sm text-muted-foreground">No reward components recorded.</p>}
      </div>
      {step.hardViolations.length ? (
        <div className="mt-4 rounded-md border border-safety/25 bg-safety-muted p-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-safety"><ShieldAlert className="size-3.5" aria-hidden="true" />Hard violations</p>
          <ul className="mt-2 space-y-1 font-mono text-xs text-safety">
            {step.hardViolations.map((violation) => <li key={violation}>{violation}</li>)}
          </ul>
        </div>
      ) : (
        <p className="mt-4 text-xs text-evidence-foreground">No hard violations on this step.</p>
      )}
      {step.observationManifestHash || step.stateBeforeHash || step.stateAfterHash ? (
        <dl className="mt-4 grid gap-2 border-t border-border pt-3 text-[11px] sm:grid-cols-3">
          {step.observationManifestHash ? <div><dt className="text-muted-foreground">Observation manifest</dt><dd className="mt-1 break-all font-mono">{step.observationManifestHash}</dd></div> : null}
          {step.stateBeforeHash ? <div><dt className="text-muted-foreground">State before</dt><dd className="mt-1 break-all font-mono">{step.stateBeforeHash}</dd></div> : null}
          {step.stateAfterHash ? <div><dt className="text-muted-foreground">State after</dt><dd className="mt-1 break-all font-mono">{step.stateAfterHash}</dd></div> : null}
        </dl>
      ) : null}
      {step.terminated ? <p className="mt-3 text-xs font-medium">Terminated: {formatLabel(step.terminationReason ?? "scenario complete")}</p> : null}
    </li>
  );
}

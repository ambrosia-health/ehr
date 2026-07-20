import { CheckCircle2, Database, ShieldCheck } from "lucide-react";

import { formatDate, formatLabel } from "@/components/learning/format";
import { StatusBadge } from "@/components/learning/status-badge";
import type { DatasetManifest } from "@/components/learning/types";

interface DatasetsPanelProps {
  datasets: DatasetManifest[];
}

export function DatasetsPanel({ datasets }: DatasetsPanelProps) {
  if (datasets.length === 0) {
    return <p className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">No governed dataset manifests are available.</p>;
  }

  return (
    <section aria-labelledby="dataset-manifests-title">
      <div className="mb-4">
        <h2 id="dataset-manifests-title" className="text-base font-semibold">Dataset manifests</h2>
        <p className="mt-1 text-sm text-muted-foreground">Release metadata and lineage only. Dataset membership and raw content are not exposed here.</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        {datasets.map((dataset) => (
          <article key={dataset.id} className="rounded-lg border border-border bg-card p-5">
            <div className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-evidence-muted text-evidence">
                <Database className="size-4" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold">{dataset.name}</h3>
                  <StatusBadge label={`v${dataset.version}`} />
                  <StatusBadge label={formatLabel(dataset.status)} tone={dataset.status === "released" ? "good" : "warning"} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">Schema {dataset.schemaVersion} · {dataset.rowCount.toLocaleString()} release items</p>
              </div>
            </div>
            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted-foreground">Classification</dt>
                <dd className="mt-1 flex items-center gap-1.5 font-medium"><ShieldCheck className="size-3.5 text-evidence" aria-hidden="true" />{formatLabel(dataset.classification)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Contains PHI</dt>
                <dd className="mt-1 flex items-center gap-1.5 font-medium"><CheckCircle2 className="size-3.5 text-evidence" aria-hidden="true" />{dataset.containsPhi === null ? "Not disclosed" : dataset.containsPhi ? "Yes" : "No"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Released</dt>
                <dd className="mt-1 font-medium">{formatDate(dataset.releasedAt)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Manifest hash</dt>
                <dd className="mt-1 break-all font-mono text-[11px]" title={dataset.hash}>{dataset.hash}</dd>
              </div>
            </dl>
            <div className="mt-5 border-t border-border pt-4 text-xs">
              <p className="font-semibold text-muted-foreground">Approved purposes</p>
              <p className="mt-1 leading-5">{dataset.purpose.length ? dataset.purpose.map(formatLabel).join(" · ") : "None recorded"}</p>
              <p className="mt-3 font-semibold text-muted-foreground">Prohibited uses</p>
              <p className="mt-1 leading-5">{dataset.prohibitedUses.length ? dataset.prohibitedUses.map(formatLabel).join(" · ") : "None recorded"}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

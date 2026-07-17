"use client";

import { BarChart3, Calculator, CheckCircle2, Clock3, HeartPulse, Info, ShieldCheck, Sparkles, UsersRound } from "lucide-react";

import { EmptyState, PageHeader, SectionHeader, StatusBadge } from "@/components/product/page-elements";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { formatInTimeZone } from "@/lib/date";

const metricGroups = [
  { label: "Growth & access", ids: ["conversion", "noshow", "response", "satisfaction"] },
  { label: "Clinical operations", ids: ["sign", "path_open", "path_closure", "doc", "avoided"] },
  { label: "Revenue performance", ids: ["accept", "denial", "ar", "revenue"] },
] as const;

function metricSignal(score: number | null): string {
  if (score == null) return "Insufficient data";
  if (score >= 100) return "On target";
  if (score >= 70) return "Near target";
  return "Needs action";
}

export function MsoDashboard() {
  const { data, mode, error, refetch } = useDemoBootstrap();
  if (mode === "loading") return <PageLoading label="Calculating MSO performance" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  if (data.session.persona !== "owner" && !data.session.presenter) return <WorkspaceUnavailable title="MSO intelligence is restricted to the owner role" />;

  const asOf = formatInTimeZone(data.scenario.currentTime, data.organization.timezone, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
  const sourceCount = new Set(data.metrics.map((metric) => metric.source)).size;
  const avoidedMetric = data.metrics.find((metric) => metric.id === "avoided");
  const engagementMetric = data.metrics.find((metric) => metric.id === "satisfaction");

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="MSO intelligence" title="Practice performance" description={`Computed from durable Ambrosia records through ${asOf}. Every measure stays attached to its target, supporting count, source records, and calculation assumption.`} />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="MSO summary">
        <Card><CardContent className="p-4"><div className="flex items-center justify-between"><span className="flex size-9 items-center justify-center rounded-lg bg-primary/8 text-primary"><BarChart3 className="size-4" /></span><StatusBadge tone="success">Live calculation</StatusBadge></div><p className="mt-4 font-mono text-3xl font-semibold tracking-[-0.05em]">{data.metrics.length}</p><p className="text-xs font-medium">Computed operating measures</p><p className="mt-2 text-[10px] text-muted-foreground">Returned by the MSO analytics read model</p></CardContent></Card>
        <Card><CardContent className="p-4"><div className="flex items-center justify-between"><span className="flex size-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700"><CheckCircle2 className="size-4" /></span><StatusBadge tone="info">Traceable</StatusBadge></div><p className="mt-4 font-mono text-3xl font-semibold tracking-[-0.05em]">{sourceCount}</p><p className="text-xs font-medium">Durable record sources</p><p className="mt-2 text-[10px] text-muted-foreground">Each measure includes support and assumptions</p></CardContent></Card>
        <Card><CardContent className="p-4"><div className="flex items-center justify-between"><span className="flex size-9 items-center justify-center rounded-lg bg-violet-50 text-violet-700"><Sparkles className="size-4" /></span><StatusBadge tone={avoidedMetric?.value == null ? "neutral" : "ai"}>{avoidedMetric?.value == null ? "Insufficient data" : "Workflow-derived"}</StatusBadge></div><p className="mt-4 font-mono text-3xl font-semibold tracking-[-0.05em]">{avoidedMetric?.value ?? "N/A"}</p><p className="text-xs font-medium">Staff work avoided</p><p className="mt-2 text-[10px] text-muted-foreground">{avoidedMetric?.supportingCount ?? "No supporting records"}</p></CardContent></Card>
        <Card><CardContent className="p-4"><div className="flex items-center justify-between"><span className="flex size-9 items-center justify-center rounded-lg bg-sky-50 text-sky-700"><HeartPulse className="size-4" /></span><StatusBadge tone={engagementMetric?.value == null ? "neutral" : "info"}>{engagementMetric?.value == null ? "Insufficient data" : "Engagement proxy"}</StatusBadge></div><p className="mt-4 font-mono text-3xl font-semibold tracking-[-0.05em]">{engagementMetric?.value ?? "N/A"}</p><p className="text-xs font-medium">Message read rate</p><p className="mt-2 text-[10px] text-muted-foreground">{engagementMetric?.supportingCount ?? "No supporting records"}</p></CardContent></Card>
      </section>

      {data.metrics.length === 0 ? <EmptyState icon={<BarChart3 className="size-6" />} title="No performance data" description="Metrics will appear after the selected period has durable appointments, encounters, pathology events, and claim events." /> : (
        <div className="space-y-5">
          {metricGroups.map((group) => {
            const metrics = group.ids.map((id) => data.metrics.find((metric) => metric.id === id)).filter(Boolean);
            if (!metrics.length) return null;
            return (
              <section key={group.label}>
                <div className="mb-3 flex items-center gap-2"><h2 className="text-sm font-semibold">{group.label}</h2><span className="font-mono text-[10px] text-muted-foreground">{metrics.length} measures</span></div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {metrics.map((metric) => {
                    const insufficientData = metric!.value == null || metric!.score == null;
                    return (
                    <Card key={metric!.id} className="overflow-hidden" data-testid={`mso-metric-${metric!.id}`} data-status={insufficientData ? "insufficient-data" : "calculated"}>
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between gap-3"><p className="min-w-0 text-xs font-medium leading-4 text-muted-foreground">{metric!.label}</p><StatusBadge tone={insufficientData ? "neutral" : metric!.tone} className="shrink-0"><Calculator className="size-3" />{metricSignal(metric!.score)}</StatusBadge></div>
                        <p className="mt-4 font-mono text-2xl font-semibold tracking-[-0.04em]">{metric!.value ?? "N/A"}</p>
                        <div className="mt-4 space-y-2 border-t pt-3 text-[10px]"><div className="flex justify-between gap-3"><span className="text-muted-foreground">Target</span><span className="text-right font-medium">{metric!.target}</span></div><div className="flex justify-between gap-3"><span className="text-muted-foreground">Support</span><span className="text-right font-medium">{metric!.supportingCount}</span></div><div className="flex justify-between gap-3"><span className="text-muted-foreground">Source</span><span className="truncate text-right font-medium">{metric!.source}</span></div></div>
                      </CardContent>
                    </Card>
                  );})}
                </div>
              </section>
            );
          })}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <Card><CardHeader className="border-b pb-3"><SectionHeader title="Calculation notes" description="Transparent assumptions behind each executive measure." action={<Info className="size-4 text-primary" />} /></CardHeader><CardContent className="grid gap-3 p-4 md:grid-cols-2">{data.metrics.map((metric) => <div key={metric.id} className="rounded-lg border p-3"><div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold">{metric.label}</p><span className="font-mono text-[9px] text-muted-foreground">{metric.source}</span></div><p className="mt-1 text-[10px] leading-4 text-muted-foreground">{metric.assumption}</p></div>)}</CardContent></Card>
        <Card><CardHeader className="border-b pb-3"><SectionHeader title="Operating work in view" description="Open queues that can change the next performance period." action={<UsersRound className="size-4 text-primary" />} /></CardHeader><CardContent className="space-y-2 p-3">{data.queues.map((queue) => <div key={queue.id} className="flex items-center gap-3 rounded-lg border p-3"><span className="flex size-8 items-center justify-center rounded-md bg-muted">{queue.id === "claims" ? <CircleDollarSignIcon /> : queue.id === "path" ? <ShieldCheck className="size-4" /> : <Clock3 className="size-4" />}</span><div className="min-w-0 flex-1"><p className="text-xs font-semibold">{queue.label}</p><p className="text-[10px] text-muted-foreground">{queue.detail}</p></div><StatusBadge tone={queue.tone} className="font-mono">{queue.count}</StatusBadge></div>)}</CardContent></Card>
      </div>
    </div>
  );
}

function CircleDollarSignIcon() {
  return <span className="font-mono text-xs font-semibold">$</span>;
}

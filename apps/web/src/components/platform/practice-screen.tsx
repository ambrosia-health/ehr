"use client";

import {
  CheckCircle2,
  ChevronDown,
  Circle,
  Clock3,
  FileCheck2,
  ReceiptText,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";

import { cn } from "@/lib/utils";

import { formatWorkspaceDate } from "./product-workspace";
import { useProductWorkspace } from "./product-workspace-provider";
import { ScreenFrame } from "./platform-ui";

interface WorkStatus {
  label: string;
  value: number;
  description: string;
  icon: typeof Circle;
  tone: "teal" | "amber" | "blue";
}

interface AutomationDomain {
  name: string;
  description: string;
  value: number;
}

function WorkStatusMetric({ description, icon: Icon, label, tone, value }: WorkStatus) {
  const toneClassName = { teal: "border-[#9ed8cf] bg-[#effaf7] text-[#0f6d65]", amber: "border-[#f2ce8f] bg-[#fff9ed] text-[#9a4d08]", blue: "border-[#b8d2f4] bg-[#f2f7ff] text-[#245c9d]" }[tone];
  return (
    <div className="flex min-w-0 items-start gap-3 px-4 py-3.5">
      <span className={cn("flex size-7 shrink-0 items-center justify-center rounded-md border", toneClassName)}>
        <Icon className="size-3.5" fill={tone === "teal" ? "currentColor" : "none"} />
      </span>
      <div className="min-w-0">
        <dt className="text-[11px] font-semibold text-[#596477]">{label}</dt>
        <dd className="mt-0.5 font-mono text-2xl font-semibold leading-none tracking-[-0.04em] text-[#172033] tabular-nums">{value}</dd>
        <p className="mt-1.5 text-[10px] leading-4 text-[#7b8495]">{description}</p>
      </div>
    </div>
  );
}

function AutomationHealthRow({ description, name, value }: AutomationDomain) {
  return <li className="grid gap-3 border-t border-[#e1e6ee] px-4 py-3.5 sm:grid-cols-[minmax(0,1fr)_110px_100px] sm:items-center sm:gap-5"><div className="min-w-0"><h3 className="text-xs font-semibold text-[#273247]">{name}</h3><p className="mt-1 truncate text-[10px] text-[#697386]">{description}</p></div><div className="h-1.5 overflow-hidden rounded-full bg-[#e3e8ef]" role="progressbar" aria-label={`${name} automation health`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}><div className="h-full rounded-full bg-[#158078]" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div><div className="flex items-baseline gap-2 sm:block sm:text-right"><span className="font-mono text-xs font-semibold text-[#0f6d65] tabular-nums">{value}%</span><span className="text-[9px] text-[#7b8495] sm:mt-0.5 sm:block">measured</span></div></li>;
}

export function PracticeScreen() {
  const { workspace } = useProductWorkspace();
  const needsClinician = workspace.queues.filter((queue) => ["path", "notes", "messages"].includes(queue.id)).reduce((sum, queue) => sum + queue.count, 0);
  const openWork = workspace.queues.reduce((sum, queue) => sum + queue.count, 0);
  const staffReviews = workspace.conversations.filter((conversation) => conversation.risk !== "routine").length;
  const preparationScore = workspace.commandCenter.scheduledVisits === 0 ? 100 : Math.round(100 * workspace.commandCenter.summariesPrepared / workspace.commandCenter.scheduledVisits);
  const workStatuses: WorkStatus[] = [
    { label: "Scheduled", value: workspace.commandCenter.scheduledVisits, description: "Visits in the current operating day", icon: Circle, tone: "teal" },
    { label: "Open work", value: openWork, description: "Items in tenant-scoped durable queues", icon: Clock3, tone: "amber" },
    { label: "Needs clinician", value: needsClinician, description: "Notes, results, and messages awaiting review", icon: needsClinician ? Clock3 : CheckCircle2, tone: "blue" },
  ];
  const automationDomains: AutomationDomain[] = [
    { name: "Visit readiness", description: "Current scheduled appointments", value: workspace.commandCenter.readinessPercent },
    { name: "Clinical preparation", description: "Summaries prepared for scheduled visits", value: Math.min(100, preparationScore) },
    { name: "Diagnostic closure", description: "Pathology closed inside policy window", value: workspace.commandCenter.pathologyClosurePercent },
    { name: "Documentation support", description: "Encounters with documentation support", value: workspace.commandCenter.documentationSupportPercent },
  ];
  const latestEvents = workspace.patient.recentEvents.slice(0, 4);
  const metricSources = [...new Set(workspace.metrics.map((metric) => metric.source))];

  return (
    <ScreenFrame className="bg-[#f8fafc] text-[#172033]">
      <main className="mx-auto max-w-[1240px] px-4 py-6 sm:px-7 lg:px-10 lg:py-8">
        <header className="flex flex-col gap-4 border-b border-[#d8dee8] pb-5 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#0b5fc6]">Practice operations</p><h1 className="mt-2 text-2xl font-semibold tracking-[-0.035em] text-[#101828]">{needsClinician === 0 ? "Practice is running." : "Practice needs review."}</h1><p className="mt-1.5 text-xs leading-5 text-[#667085]">{needsClinician === 0 ? "No clinical work is waiting on you." : `${needsClinician} clinical queue items are waiting on you.`}</p></div><div className="flex flex-col gap-1 text-[10px] sm:items-end"><span className={cn("inline-flex items-center gap-1.5 font-semibold", staffReviews === 0 ? "text-[#0f6d65]" : "text-[#9a4d08]")}><ShieldCheck className="size-3.5" />{staffReviews} staff-review {staffReviews === 1 ? "thread" : "threads"}</span><span className="text-[#7b8495]">Snapshot {formatWorkspaceDate(workspace.scenario.currentTime, workspace, { hour: "numeric", minute: "2-digit" })}</span></div></header>

        <section className="mt-5 overflow-hidden rounded-lg border border-[#d8dee8] bg-white" aria-labelledby="operations-summary-heading"><div className="flex flex-col gap-2 border-b border-[#d8dee8] bg-[#f8fafc] px-4 py-3 sm:flex-row sm:items-center sm:justify-between"><h2 id="operations-summary-heading" className="text-sm font-semibold text-[#1d2939]">Operations summary</h2><p className={cn("inline-flex items-center gap-1.5 text-[10px] font-medium", needsClinician === 0 ? "text-[#0f6d65]" : "text-[#9a4d08]")}><CheckCircle2 className="size-3.5" />{needsClinician === 0 ? "No clinical work is waiting on you." : "Review the clinical work queue."}</p></div><dl className="grid divide-y divide-[#dfe4ec] sm:grid-cols-3 sm:divide-x sm:divide-y-0">{workStatuses.map((status) => <WorkStatusMetric key={status.label} {...status} />)}</dl></section>

        <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.65fr)]">
          <section className="overflow-hidden rounded-lg border border-[#d8dee8] bg-white" aria-labelledby="automation-health-heading"><div className="flex items-start justify-between gap-4 px-4 py-3.5"><div><h2 id="automation-health-heading" className="text-sm font-semibold text-[#1d2939]">Automation health</h2><p className="mt-1 text-[10px] text-[#697386]">Calculated from the current database snapshot.</p></div><span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-[#0f6d65]"><CheckCircle2 className="size-3.5" />Current snapshot</span></div><div className="hidden grid-cols-[minmax(0,1fr)_110px_100px] gap-5 border-t border-[#d8dee8] bg-[#f8fafc] px-4 py-2 text-[9px] font-semibold uppercase tracking-[0.1em] text-[#667085] sm:grid"><span>Domain</span><span>Health</span><span className="text-right">Source</span></div><ul>{automationDomains.map((domain) => <AutomationHealthRow key={domain.name} {...domain} />)}</ul><div className="flex flex-col gap-1 border-t border-[#d8dee8] bg-[#f8fafc] px-4 py-2.5 text-[9px] text-[#697386] sm:flex-row sm:items-center sm:justify-between"><span>{workspace.organization.name}</span><span>{workspace.scenario.modelMode.replaceAll("_", " ")}</span></div></section>

          <aside className="overflow-hidden rounded-lg border border-[#d8dee8] bg-white" aria-labelledby="admin-receipts-heading"><div className="flex items-start gap-2.5 px-4 py-3.5"><ReceiptText className="mt-0.5 size-4 shrink-0 text-[#0b5fc6]" /><div><h2 id="admin-receipts-heading" className="text-sm font-semibold text-[#1d2939]">Recent durable activity</h2><p className="mt-1 text-[10px] text-[#697386]">Records returned by the workspace endpoint.</p></div></div><ol>{latestEvents.map((event) => <li key={event.id} className="grid grid-cols-[70px_minmax(0,1fr)] gap-3 border-t border-[#e1e6ee] px-4 py-3.5"><time className="font-mono text-[9px] text-[#7b8495]" dateTime={event.occurredAt}>{formatWorkspaceDate(event.occurredAt, workspace, { month: "short", day: "numeric" })}</time><div><p className="flex items-start gap-2 text-[11px] font-semibold leading-4 text-[#273247]"><FileCheck2 className="mt-0.5 size-3.5 shrink-0 text-[#0f766e]" />{event.title}</p><p className="mt-1 text-[10px] leading-4 text-[#697386]">{event.detail}</p></div></li>)}</ol><p className="border-t border-[#d8dee8] bg-[#f8fafc] px-4 py-2.5 text-[10px] font-medium text-[#245c9d]">{latestEvents.length} recent records shown</p></aside>
        </div>

        <details className="group mt-5 overflow-hidden rounded-lg border border-[#d8dee8] bg-white"><summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0b5fc6] [&::-webkit-details-marker]:hidden"><SlidersHorizontal className="size-4 shrink-0 text-[#0b5fc6]" /><span className="min-w-0 flex-1"><span className="block text-xs font-semibold text-[#273247]">Data provenance</span><span className="mt-0.5 block text-[10px] text-[#697386]">Current note, queue, model, and metric sources</span></span><ChevronDown className="size-4 shrink-0 text-[#697386] transition-transform group-open:rotate-180" /></summary><dl className="grid border-t border-[#d8dee8] sm:grid-cols-2 lg:grid-cols-4">{[["Note record", `Version ${workspace.encounter.note.currentVersion.number} · ${workspace.encounter.note.status}`], ["Durable queues", `${workspace.queues.length} queues · ${openWork} open items`], ["Model mode", workspace.scenario.modelMode.replaceAll("_", " ")], ["Metric sources", metricSources.join(" · ") || "No metric sources"]].map(([label, value], index) => <div key={label} className={cn("px-4 py-3.5", index > 0 && "border-t border-[#e1e6ee] sm:border-l sm:border-t-0", index === 2 && "sm:border-l-0 sm:border-t lg:border-l lg:border-t-0")}><dt className="text-[9px] font-semibold uppercase tracking-[0.1em] text-[#7b8495]">{label}</dt><dd className="mt-1.5 text-[11px] font-medium leading-4 text-[#344054]">{value}</dd></div>)}</dl></details>
      </main>
    </ScreenFrame>
  );
}

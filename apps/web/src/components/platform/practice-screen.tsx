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

import { ScreenFrame } from "./platform-ui";

const workStatuses = [
  {
    label: "Moving",
    value: "309",
    description: "Patient journeys advancing",
    icon: Circle,
    tone: "teal",
  },
  {
    label: "Waiting externally",
    value: "7",
    description: "Monitored outside the practice",
    icon: Clock3,
    tone: "amber",
  },
  {
    label: "Needs you",
    value: "0",
    description: "No clinician decisions queued",
    icon: CheckCircle2,
    tone: "blue",
  },
] as const;

const automationDomains = [
  {
    name: "Front desk",
    description: "Scheduling, intake, eligibility and reminders",
    value: 100,
    widthClassName: "w-full",
  },
  {
    name: "Clinical preparation",
    description: "Chart summaries, records and patient follow-up",
    value: 99.8,
    widthClassName: "w-[99.8%]",
  },
  {
    name: "Revenue cycle",
    description: "Coding, claims, denials and patient balances",
    value: 99.6,
    widthClassName: "w-[99.6%]",
  },
] as const;

const adminReceipts = [
  {
    time: "7:48 AM",
    dateTime: "2026-07-17T07:48:00-04:00",
    title: "Eligibility and intake reconciled",
    detail: "18 appointments · no exceptions",
  },
  {
    time: "8:02 AM",
    dateTime: "2026-07-17T08:02:00-04:00",
    title: "Patient reminders completed",
    detail: "27 delivered · 3 rescheduled automatically",
  },
  {
    time: "8:16 AM",
    dateTime: "2026-07-17T08:16:00-04:00",
    title: "Clean claims queued",
    detail: "11 visits · $9,840 ready",
  },
  {
    time: "8:24 AM",
    dateTime: "2026-07-17T08:24:00-04:00",
    title: "Pathology follow-up monitored",
    detail: "6 results matched · 0 safety risks",
  },
] as const;

const advancedControls = [
  ["Automation policy", "v3.4.2 · approved Jul 10"],
  ["Connected systems", "12 healthy · 0 degraded"],
  ["Audit coverage", "100% of actions recorded"],
  ["Billing guardrail", "Unsupported coding always stops"],
] as const;

type WorkStatus = (typeof workStatuses)[number];
type AutomationDomain = (typeof automationDomains)[number];

function WorkStatusMetric({ description, icon: Icon, label, tone, value }: WorkStatus) {
  const toneClassName = {
    teal: "border-[#9ed8cf] bg-[#effaf7] text-[#0f6d65]",
    amber: "border-[#f2ce8f] bg-[#fff9ed] text-[#9a4d08]",
    blue: "border-[#b8d2f4] bg-[#f2f7ff] text-[#245c9d]",
  }[tone];

  return (
    <div className="flex min-w-0 items-start gap-3 px-4 py-3.5">
      <span className={cn("flex size-7 shrink-0 items-center justify-center rounded-md border", toneClassName)}>
        <Icon className="size-3.5" fill={tone === "teal" ? "currentColor" : "none"} aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <dt className="text-[11px] font-semibold text-[#596477]">{label}</dt>
        <dd className="mt-0.5 font-mono text-2xl font-semibold leading-none tracking-[-0.04em] text-[#172033] tabular-nums">{value}</dd>
        <p className="mt-1.5 text-[10px] leading-4 text-[#7b8495]">{description}</p>
      </div>
    </div>
  );
}

function AutomationHealthRow({ description, name, value, widthClassName }: AutomationDomain) {
  return (
    <li className="grid gap-3 border-t border-[#e1e6ee] px-4 py-3.5 sm:grid-cols-[minmax(0,1fr)_110px_100px] sm:items-center sm:gap-5">
      <div className="min-w-0">
        <h3 className="text-xs font-semibold text-[#273247]">{name}</h3>
        <p className="mt-1 truncate text-[10px] text-[#697386]">{description}</p>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-[#e3e8ef]"
        role="progressbar"
        aria-label={`${name} automation health`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
      >
        <div className={cn("h-full rounded-full bg-[#158078]", widthClassName)} />
      </div>
      <div className="flex items-baseline gap-2 sm:block sm:text-right">
        <span className="font-mono text-xs font-semibold text-[#0f6d65] tabular-nums">{value}%</span>
        <span className="text-[9px] text-[#7b8495] sm:mt-0.5 sm:block">automatic</span>
      </div>
    </li>
  );
}

function AdminReceipt({ dateTime, detail, time, title }: (typeof adminReceipts)[number]) {
  return (
    <li className="grid grid-cols-[62px_minmax(0,1fr)] gap-3 border-t border-[#e1e6ee] px-4 py-3.5">
      <time className="font-mono text-[9px] text-[#7b8495] tabular-nums" dateTime={dateTime}>{time}</time>
      <div className="min-w-0">
        <p className="flex items-start gap-2 text-[11px] font-semibold leading-4 text-[#273247]">
          <FileCheck2 className="mt-0.5 size-3.5 shrink-0 text-[#0f766e]" aria-hidden="true" />
          <span>{title}</span>
        </p>
        <p className="mt-1 text-[10px] leading-4 text-[#697386]">{detail}</p>
      </div>
    </li>
  );
}

export function PracticeScreen() {
  return (
    <ScreenFrame className="bg-[#f8fafc] text-[#172033]">
      <main className="mx-auto max-w-[1240px] px-4 py-6 sm:px-7 lg:px-10 lg:py-8">
        <header className="flex flex-col gap-4 border-b border-[#d8dee8] pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#0b5fc6]">Practice operations</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-[-0.035em] text-[#101828]">Practice is running.</h1>
            <p className="mt-1.5 text-xs leading-5 text-[#667085]">The work is moving quietly. Nothing needs your attention.</p>
          </div>
          <div className="flex flex-col gap-1 text-[10px] sm:items-end">
            <span className="inline-flex items-center gap-1.5 font-semibold text-[#0f6d65]">
              <ShieldCheck className="size-3.5" aria-hidden="true" />
              0 safety risks
            </span>
            <span className="text-[#7b8495]">Last checked 40 seconds ago</span>
          </div>
        </header>

        <section className="mt-5 overflow-hidden rounded-lg border border-[#d8dee8] bg-white" aria-labelledby="operations-summary-heading">
          <div className="flex flex-col gap-2 border-b border-[#d8dee8] bg-[#f8fafc] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 id="operations-summary-heading" className="text-sm font-semibold text-[#1d2939]">Operations summary</h2>
            <p className="inline-flex items-center gap-1.5 text-[10px] font-medium text-[#0f6d65]">
              <CheckCircle2 className="size-3.5" aria-hidden="true" />
              No office work is waiting on you.
            </p>
          </div>
          <dl className="grid divide-y divide-[#dfe4ec] sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {workStatuses.map((status) => <WorkStatusMetric key={status.label} {...status} />)}
          </dl>
        </section>

        <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.65fr)]">
          <section className="overflow-hidden rounded-lg border border-[#d8dee8] bg-white" aria-labelledby="automation-health-heading">
            <div className="flex items-start justify-between gap-4 px-4 py-3.5">
              <div>
                <h2 id="automation-health-heading" className="text-sm font-semibold text-[#1d2939]">Automation health</h2>
                <p className="mt-1 text-[10px] text-[#697386]">Core systems operating under approved policy.</p>
              </div>
              <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-[#0f6d65]">
                <CheckCircle2 className="size-3.5" aria-hidden="true" />
                All healthy
              </span>
            </div>
            <div className="hidden grid-cols-[minmax(0,1fr)_110px_100px] gap-5 border-t border-[#d8dee8] bg-[#f8fafc] px-4 py-2 text-[9px] font-semibold uppercase tracking-[0.1em] text-[#667085] sm:grid">
              <span>Domain</span>
              <span>Health</span>
              <span className="text-right">Mode</span>
            </div>
            <ul>
              {automationDomains.map((domain) => <AutomationHealthRow key={domain.name} {...domain} />)}
            </ul>
            <div className="flex flex-col gap-1 border-t border-[#d8dee8] bg-[#f8fafc] px-4 py-2.5 text-[9px] text-[#697386] sm:flex-row sm:items-center sm:justify-between">
              <span>All connections healthy</span>
              <span>Policies and source links verified</span>
            </div>
          </section>

          <aside className="overflow-hidden rounded-lg border border-[#d8dee8] bg-white" aria-labelledby="admin-receipts-heading">
            <div className="flex items-start gap-2.5 px-4 py-3.5">
              <ReceiptText className="mt-0.5 size-4 shrink-0 text-[#0b5fc6]" aria-hidden="true" />
              <div>
                <h2 id="admin-receipts-heading" className="text-sm font-semibold text-[#1d2939]">Today&apos;s admin receipts</h2>
                <p className="mt-1 text-[10px] text-[#697386]">Completed work, recorded as it happened.</p>
              </div>
            </div>
            <ol>
              {adminReceipts.map((receipt) => <AdminReceipt key={`${receipt.dateTime}-${receipt.title}`} {...receipt} />)}
            </ol>
            <p className="border-t border-[#d8dee8] bg-[#f8fafc] px-4 py-2.5 text-[10px] font-medium text-[#245c9d]">
              31 routine actions completed today
            </p>
          </aside>
        </div>

        <details className="group mt-5 overflow-hidden rounded-lg border border-[#d8dee8] bg-white">
          <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0b5fc6] [&::-webkit-details-marker]:hidden">
            <SlidersHorizontal className="size-4 shrink-0 text-[#0b5fc6]" aria-hidden="true" />
            <span className="min-w-0 flex-1">
              <span className="block text-xs font-semibold text-[#273247]">Advanced controls</span>
              <span className="mt-0.5 block text-[10px] text-[#697386]">Policies, integrations, billing rules and audit history</span>
            </span>
            <ChevronDown className="size-4 shrink-0 text-[#697386] transition-transform group-open:rotate-180" aria-hidden="true" />
          </summary>
          <dl className="grid border-t border-[#d8dee8] sm:grid-cols-2 lg:grid-cols-4">
            {advancedControls.map(([label, value], index) => (
              <div key={label} className={cn("px-4 py-3.5", index > 0 && "border-t border-[#e1e6ee] sm:border-l sm:border-t-0", index === 2 && "sm:border-l-0 sm:border-t lg:border-l lg:border-t-0")}>
                <dt className="text-[9px] font-semibold uppercase tracking-[0.1em] text-[#7b8495]">{label}</dt>
                <dd className="mt-1.5 text-[11px] font-medium leading-4 text-[#344054]">{value}</dd>
              </div>
            ))}
          </dl>
        </details>
      </main>
    </ScreenFrame>
  );
}

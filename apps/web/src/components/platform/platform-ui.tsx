"use client";

import {
  ArrowRight,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  Command,
  LoaderCircle,
  Octagon,
  Search,
  Send,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import type { JourneyStatus, JourneyStep } from "./platform-data";

export function ScreenFrame({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("min-h-[calc(100vh-4.75rem)] bg-[#fbfaf6] pb-24 text-[#15392c]", className)}>{children}</div>;
}

export function ScreenHeader({
  title,
  description,
  action,
  eyebrow,
}: {
  title: ReactNode;
  description: string;
  action?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <header className="border-b border-[#dce3db] px-5 py-7 sm:px-8 lg:px-10">
      <div className="mx-auto flex max-w-[1480px] flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-4xl">
          {eyebrow ? <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#61746b]">{eyebrow}</p> : null}
          <h1 className="text-[clamp(2rem,3.3vw,3.5rem)] font-semibold leading-[1.02] tracking-[-0.055em] text-[#103b2b]">{title}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[#5c6d65] sm:text-base">{description}</p>
        </div>
        {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
      </div>
    </header>
  );
}

const statusConfig: Record<JourneyStatus, { icon: typeof Check; label: string; className: string }> = {
  complete: { icon: Check, label: "Completed", className: "border-[#1e5a42] bg-[#1e5a42] text-white" },
  moving: { icon: Circle, label: "Advancing", className: "border-[#5e8b77] bg-[#fbfaf6] text-[#2f6a50]" },
  waiting: { icon: Clock3, label: "Waiting", className: "border-[#9aa8a0] bg-[#fbfaf6] text-[#67776f]" },
  human: { icon: Octagon, label: "Waiting for you", className: "border-[#cb7200] bg-[#fff7e9] text-[#ba6500]" },
  risk: { icon: TriangleAlert, label: "At risk", className: "border-[#bb4b3a] bg-[#fff1ef] text-[#a63e30]" },
};

export function StateMark({ status, className }: { status: JourneyStatus; className?: string }) {
  const config = statusConfig[status];
  const Icon = config.icon;
  return (
    <span className={cn("inline-flex size-6 shrink-0 items-center justify-center rounded-full border-2", config.className, className)} title={config.label}>
      <Icon className="size-3" strokeWidth={2.4} />
      <span className="sr-only">{config.label}</span>
    </span>
  );
}

export function StatusPill({ status, children }: { status: JourneyStatus; children: ReactNode }) {
  const config = statusConfig[status];
  const Icon = config.icon;
  return (
    <span className={cn("inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-[10px] font-semibold", config.className)}>
      <Icon className="size-3" />{children}
    </span>
  );
}

export function PatientMark({ initials, size = "md" }: { initials: string; size?: "sm" | "md" | "lg" }) {
  return (
    <span className={cn(
      "inline-flex shrink-0 items-center justify-center rounded-full border border-[#c8d3cb] bg-[#dfe7df] font-semibold text-[#254b3a]",
      size === "sm" && "size-7 text-[10px]",
      size === "md" && "size-10 text-xs",
      size === "lg" && "size-14 text-sm",
    )}>{initials}</span>
  );
}

export function CareRail({ steps, compact = false }: { steps: JourneyStep[]; compact?: boolean }) {
  return (
    <div
      className={cn("grid", compact ? "min-w-[420px] gap-0" : "min-w-[760px] gap-1")}
      style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(${compact ? 46 : 105}px, 1fr))` }}
    >
      {steps.map((step, index) => (
        <div key={`${step.label}-${index}`} className="relative min-w-0 pr-3">
          {index < steps.length - 1 ? <span className={cn("absolute left-5 right-0 top-3 h-px", step.status === "human" ? "bg-[#d28a29]" : step.status === "complete" ? "bg-[#3f775d]" : "bg-[#9eb9aa]")} aria-hidden="true" /> : null}
          <div className="relative z-10"><StateMark status={step.status} /></div>
          <p className={cn("mt-3 truncate font-semibold", compact ? "text-[10px]" : "text-[11px]", step.status === "human" && "text-[#b65d00]")}>{step.label}</p>
          <p className={cn("mt-1 leading-4 text-[#42554c]", compact ? "truncate text-[9px]" : "text-[10px]")}>{step.detail}</p>
          {step.meta ? <p className={cn("mt-0.5 leading-4 text-[#718078]", compact ? "truncate text-[9px]" : "text-[10px]")}>{step.meta}</p> : null}
        </div>
      ))}
    </div>
  );
}

export function HorizonTabs({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const options = ["Now", "24 hours", "7 days", "30 days", "Surveillance"];
  return (
    <div className="flex overflow-x-auto border-b border-[#dce3db] px-5 sm:px-8 lg:px-10" role="tablist" aria-label="Care horizon">
      <div className="mx-auto flex w-full max-w-[1480px] min-w-max">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            role="tab"
            aria-selected={value === option}
            onClick={() => onChange(option)}
            className={cn("border-b-2 px-5 py-4 text-left text-xs transition-colors", value === option ? "border-[#1f5c43] font-semibold text-[#153f30]" : "border-transparent text-[#697a72] hover:text-[#214936]")}
          >
            <span className="block">{option}</span>
            <span className="mt-1 block text-[9px] font-normal text-[#87948d]">{option === "Now" ? "Needs attention" : option === "24 hours" ? "Next day" : option === "7 days" ? "Next week" : option === "30 days" ? "Next month" : "Long-term"}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function AgentDock({ context = "clinic" }: { context?: string }) {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<string | null>(null);
  const suggestions = context === "Sarah"
    ? ["compare lesion history", "prepare aftercare", "explain the estimate"]
    : context === "revenue"
      ? ["show claims likely to deny", "prepare tomorrow’s authorizations", "explain variance"]
      : ["rebalance the afternoon", "prepare biopsy follow-ups", "draft patient updates"];

  function submit() {
    if (!query.trim()) return;
    setResponse(`Ambrosia prepared a reviewable plan for “${query.trim()}”. No records changed.`);
    setQuery("");
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-[#d8e0d8] bg-[#fffefa]/96 px-4 py-2 shadow-[0_-10px_30px_rgba(19,60,44,0.05)] backdrop-blur lg:left-60">
      <div className="mx-auto flex max-w-[1480px] items-center gap-3">
        <Sparkles className="size-4 shrink-0 text-[#1f5a42]" />
        <form className="flex min-w-0 flex-1 items-center gap-2" onSubmit={(event) => { event.preventDefault(); submit(); }}>
          <Input value={query} onChange={(event) => setQuery(event.target.value)} className="h-9 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0" aria-label={`Ask ${context === "clinic" ? "Ambrosia" : `${context} agent`}`} placeholder={`Ask ${context === "clinic" ? "Ambrosia" : `${context}’s agent`} to…`} />
          <Button type="submit" variant="ghost" size="icon-sm" aria-label="Send command" disabled={!query.trim()}><Send className="size-4" /></Button>
        </form>
        <div className="hidden items-center gap-2 xl:flex">
          {suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => setQuery(suggestion)} className="rounded-md border border-[#d8e0d8] px-3 py-2 text-[10px] text-[#52665b] hover:bg-[#f1f5ef]">{suggestion}</button>)}
        </div>
      </div>
      {response ? <button type="button" onClick={() => setResponse(null)} className="absolute bottom-14 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-lg border border-[#c9d8cd] bg-white px-4 py-3 text-xs text-[#2e5141] shadow-lg"><CheckCircle2 className="size-4 text-[#26704e]" />{response}</button> : null}
    </div>
  );
}

export function PortfolioStat({ value, label, status, active = false }: { value: string; label: string; status: JourneyStatus; active?: boolean }) {
  return (
    <div className={cn("border-l border-[#d8e0d8] px-5 first:border-l-0", active && "rounded-lg border border-[#d69740] bg-[#fff8eb] py-3 first:border-l")}>
      <div className="flex items-center gap-2"><StateMark status={status} className="size-5" /><span className="font-mono text-xl font-semibold tracking-[-0.04em]">{value}</span></div>
      <p className="mt-1 text-[10px] text-[#65766d]">{label}</p>
    </div>
  );
}

export function SearchField({ value, onChange, placeholder = "Search" }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#728178]" />
      <Input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="h-10 border-[#d4ddd5] bg-white pl-9 pr-16 shadow-none" />
      <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded border border-[#d8dfd8] bg-[#f7f8f4] px-1.5 py-0.5 text-[9px] text-[#6d7b73]"><Command className="mr-0.5 inline size-2.5" />K</kbd>
    </div>
  );
}

export function SectionTitle({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div><h2 className="text-lg font-semibold tracking-[-0.025em] text-[#173f30]">{title}</h2>{description ? <p className="mt-1 text-xs leading-5 text-[#6b7a72]">{description}</p> : null}</div>
      {action}
    </div>
  );
}

export function ApprovalReceipt({ children }: { children: ReactNode }) {
  return <div className="flex items-start gap-3 rounded-xl border border-[#bcd5c4] bg-[#eef7f0] p-4 text-sm text-[#214d38]"><CheckCircle2 className="mt-0.5 size-5 shrink-0 text-[#236b48]" /><div>{children}</div></div>;
}

export function PrimaryArrow({ children, href, onClick }: { children: ReactNode; href?: string; onClick?: () => void }) {
  const className = "inline-flex h-11 items-center justify-center gap-3 rounded-lg bg-[#c76c00] px-5 text-sm font-semibold text-white shadow-[0_8px_24px_rgba(173,94,0,0.16)] transition-colors hover:bg-[#ab5e00]";
  if (href) return <Link href={href} className={className}>{children}<ArrowRight className="size-4" /></Link>;
  return <button type="button" onClick={onClick} className={className}>{children}<ArrowRight className="size-4" /></button>;
}

export function SystemStatus({ label = "Operating normally", detail = "309 journeys are advancing" }: { label?: string; detail?: string }) {
  return <div className="flex items-center gap-3"><span className="flex size-8 items-center justify-center rounded-full border border-[#aec7b6] bg-[#f0f7f1]"><Check className="size-4 text-[#215c40]" /></span><div><p className="text-xs font-semibold text-[#264b3b]">{label}</p><p className="mt-0.5 text-[10px] text-[#728078]">{detail}</p></div></div>;
}

export function LoadingAction({ children, busy }: { children: ReactNode; busy?: boolean }) {
  return <>{busy ? <LoaderCircle className="size-4 animate-spin" /> : null}{children}</>;
}

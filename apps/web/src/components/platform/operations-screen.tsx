"use client";

import {
  BadgeDollarSign,
  Beaker,
  Check,
  ChevronRight,
  CircleUserRound,
  MessageSquareText,
  ShieldCheck,
  SlidersHorizontal,
  Stethoscope,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

import { AgentDock, PatientMark, ScreenFrame, ScreenHeader, SectionTitle, StateMark, StatusPill, SystemStatus } from "./platform-ui";

const systemStages = [
  { icon: CircleUserRound, label: "Patient access", detail: "Intake & eligibility" },
  { icon: Stethoscope, label: "Clinical care", detail: "Visit & documentation" },
  { icon: Beaker, label: "Diagnostics", detail: "Orders & results" },
  { icon: MessageSquareText, label: "Communication", detail: "Messages & follow-ups" },
  { icon: BadgeDollarSign, label: "Revenue", detail: "Billing & payment" },
  { icon: ShieldCheck, label: "Closure", detail: "Care complete" },
];

const rows = [
  { initials: "SM", patient: "Sarah Mitchell", concern: "Changing lesion", stages: ["complete", "complete", "moving", "moving", "waiting", "moving"] as const, stop: null },
  { initials: "AR", patient: "Alex Rivera", concern: "Acne follow-up", stages: ["complete", "complete", "complete", "complete", "waiting", "moving"] as const, stop: null },
  { initials: "JL", patient: "Jordan Lee", concern: "Pathology follow-up", stages: ["complete", "complete", "human", "moving", "waiting", "waiting"] as const, stop: "Awaiting pathology plan" },
  { initials: "NW", patient: "Natalie Wong", concern: "Psoriasis", stages: ["complete", "complete", "waiting", "risk", "waiting", "waiting"] as const, stop: "Safety-language review" },
  { initials: "BC", patient: "Benjamin Carter", concern: "Mole check", stages: ["complete", "complete", "complete", "complete", "complete", "complete"] as const, stop: null },
];

const may = ["Schedule within approved templates", "Verify benefits and prepare estimates", "Draft notes, orders, coding, and messages", "Monitor pathology, communication, and payer SLAs", "Reconcile matched records and escalate contradictions"];
const mustStop = ["Diagnosing or choosing treatment", "Clinical signature, prescribing, or order placement", "Critical or abnormal result notification", "Unsupported coding, appeal, or medical-necessity attestation", "Patient dispute, hardship, or high-value refund"];

export function OperationsScreen() {
  const [tab, setTab] = useState("Controls");
  const [capabilities, setCapabilities] = useState<Record<string, boolean>>({ "Clinical drafting": true, "Patient coordination": true, "Revenue automation": true, "External submissions": true });

  return <ScreenFrame>
    <ScreenHeader title={<>One intelligence layer.<br />Every patient journey.</>} description="Ambrosia is advancing 312 care journeys across six clinic systems. Policies define what moves autonomously, what must stop, and who remains accountable." action={<div className="flex flex-wrap items-center gap-4"><SystemStatus detail="100% of agent actions auditable" /><Button variant="outline"><SlidersHorizontal className="size-4" />Agent controls</Button></div>} />
    <nav className="border-b border-[#dce3db] px-5 sm:px-8 lg:px-10"><div className="mx-auto flex max-w-[1480px]">{["Controls", "Intelligence", "Activity"].map((item) => <button type="button" key={item} onClick={() => setTab(item)} className={cn("border-b-2 px-5 py-4 text-xs", tab === item ? "border-[#1f5c43] font-semibold text-[#153f30]" : "border-transparent text-[#697a72]")}>{item}</button>)}</div></nav>
    <div className="mx-auto max-w-[1480px] px-5 py-7 sm:px-8 lg:px-10">
      <section className="overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">
        <div className="grid grid-cols-[220px_repeat(6,minmax(120px,1fr))] border-b border-[#e0e5df] bg-[#f5f7f3]">
          <div className="p-4 text-[9px] font-semibold uppercase tracking-[0.12em] text-[#718078]">Care journey</div>
          {systemStages.map((stage) => { const Icon = stage.icon; return <div key={stage.label} className="border-l border-[#e0e5df] p-4"><div className="flex items-center gap-2"><span className="flex size-7 items-center justify-center rounded-full border border-[#afc3b2]"><Icon className="size-3.5 text-[#2b654b]" /></span><span><span className="block text-[10px] font-semibold">{stage.label}</span><span className="mt-0.5 block text-[8px] text-[#718078]">{stage.detail}</span></span></div></div>; })}
        </div>
        <div className="overflow-x-auto">{rows.map((row) => <div key={row.patient} className="grid min-w-[980px] grid-cols-[220px_repeat(6,minmax(120px,1fr))] border-b border-[#e4e8e3] last:border-b-0"><div className="flex items-center gap-3 p-4"><PatientMark initials={row.initials} size="sm" /><div><p className="text-xs font-semibold">{row.patient}</p><p className="mt-1 text-[9px] text-[#6b7a72]">{row.concern}</p></div></div>{row.stages.map((status, index) => <div key={`${row.patient}-${index}`} className="flex items-center gap-2 border-l border-[#e4e8e3] p-4"><StateMark status={status} className="size-5" /><div><p className={cn("text-[9px] font-semibold", status === "human" && "text-[#b65d00]", status === "risk" && "text-[#a44234]")}>{status === "complete" ? "Complete" : status === "moving" ? "Advancing" : status === "human" ? row.stop : status === "risk" ? row.stop : "Waiting"}</p><p className="mt-1 text-[8px] text-[#77857d]">{status === "complete" ? "Source reconciled" : status === "moving" ? "Next step staged" : "Monitor active"}</p></div></div>)}</div>)}</div>
      </section>

      {tab === "Controls" ? <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(340px,0.7fr)]">
        <section className="rounded-xl border border-[#d9dfd8] bg-white p-5"><div className="flex items-start justify-between gap-3"><SectionTitle title="Agent controls & policy" description="Policy v3.4.2 · approved Jul 10, 2026 · 100% audit coverage" /><ShieldCheck className="size-5 text-[#2b654b]" /></div><div className="mt-6 grid gap-6 md:grid-cols-2"><div><p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#2a6147]">Ambrosia may</p><div className="mt-3 space-y-3">{may.map((item) => <div key={item} className="flex items-start gap-2 text-[10px] leading-4"><span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full bg-[#276346] text-white"><Check className="size-2.5" /></span>{item}</div>)}</div></div><div><p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#a45a05]">Ambrosia must stop before</p><div className="mt-3 space-y-3">{mustStop.map((item) => <div key={item} className="flex items-start gap-2 text-[10px] leading-4"><StateMark status="human" className="mt-0.5 size-4" />{item}</div>)}</div></div></div></section>
        <aside className="rounded-xl border border-[#d9dfd8] bg-white p-5"><SectionTitle title="Capability controls" description="Emergency stops are immediate and recorded." /><div className="mt-5 space-y-4">{Object.entries(capabilities).map(([label, enabled]) => <div key={label} className="flex items-center justify-between border-b border-[#e4e8e3] pb-4 last:border-b-0"><div><p className="text-xs font-semibold">{label}</p><p className="mt-1 text-[9px] text-[#718078]">{enabled ? "Operating under approved policy" : "Paused across the clinic"}</p></div><Switch checked={enabled} onCheckedChange={(checked) => setCapabilities((current) => ({ ...current, [label]: checked }))} aria-label={`Toggle ${label}`} /></div>)}</div></aside>
      </div> : null}

      {tab === "Intelligence" ? <div className="mt-6"><SectionTitle title="Clinic intelligence" description="Measure → cause → recommended operating change, with cohort, timeframe, sources, and assumptions." /><div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[
        ["Pathology closure", "2.1 days", "Down 0.6d", "Earlier lab reconciliation prevented 11 manual checks."],
        ["First-pass acceptance", "97.8%", "+1.9%", "Modifier support is the largest remaining preventable denial source."],
        ["Message resolution", "18 min", "Down 7m", "246 routine conversations advanced under approved policies."],
        ["Visit readiness", "96%", "+8%", "Overnight eligibility and intake reconciliation protected 41 minutes."],
        ["Admin work automated", "18.4h", "+4.2h", "Documentation and coordination drove most of the change."],
        ["Patient collection", "88%", "+3%", "EOB-linked explanations reduced balance questions."],
      ].map(([label, value, delta, insight]) => <article key={label} className="rounded-xl border border-[#d9dfd8] bg-white p-5"><div className="flex items-center justify-between"><p className="text-xs font-semibold">{label}</p><StatusPill status="complete">{delta}</StatusPill></div><p className="mt-4 font-mono text-3xl font-semibold tracking-[-0.05em]">{value}</p><p className="mt-3 text-[10px] leading-5 text-[#63736a]">{insight}</p><button type="button" className="mt-4 flex items-center gap-1 text-[10px] font-semibold text-[#245942]">View evidence <ChevronRight className="size-3" /></button></article>)}</div></div> : null}

      {tab === "Activity" ? <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_360px]"><section><SectionTitle title="Recent activity across systems" description="Append-only, source-linked, policy-versioned, and reviewable." /><div className="mt-4 overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">{[
        ["12:42 PM", "Eligibility confirmed for Emily Lopez", "Availity", "99%"],
        ["12:28 PM", "Pathology result matched to specimen", "Dermpath Labs", "98%"],
        ["12:15 PM", "Aftercare queued in patient portal", "Ambrosia", "Policy"],
        ["11:58 AM", "Denial documentation assembled for claim #98214", "Ambrosia", "94%"],
        ["11:41 AM", "Afternoon schedule rebalanced", "Ambrosia", "97%"],
      ].map(([time, action, source, confidence]) => <div key={`${time}-${action}`} className="grid gap-2 border-b border-[#e4e8e3] p-4 last:border-b-0 sm:grid-cols-[80px_1fr_140px_60px]"><span className="font-mono text-[10px] text-[#718078]">{time}</span><span className="flex items-center gap-2 text-xs font-semibold"><Check className="size-3.5 text-[#2b654b]" />{action}</span><span className="text-[10px] text-[#687870]">{source}</span><span className="text-[10px] text-[#687870]">{confidence}</span></div>)}</div></section><aside className="rounded-xl border border-[#d9dfd8] bg-white p-5"><SectionTitle title="Audit health" description="Coverage and exceptions across the operating layer." /><div className="mt-5 space-y-4">{[["Actions logged", "100%"], ["Source links valid", "99.8%"], ["Policy overrides", "2"], ["Stale approvals", "0"], ["Near misses", "1 reviewed"]].map(([label, value]) => <div key={label} className="flex justify-between border-b border-[#e4e8e3] pb-3 text-xs last:border-b-0"><span className="text-[#687870]">{label}</span><span className="font-semibold">{value}</span></div>)}</div></aside></div> : null}
    </div>
    <AgentDock />
  </ScreenFrame>;
}

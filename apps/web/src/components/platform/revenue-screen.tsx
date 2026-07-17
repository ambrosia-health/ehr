"use client";

import {
  ChevronRight,
  FileCheck2,
  Landmark,
  ReceiptText,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  UserRoundCheck,
  WalletCards,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { AgentDock, ApprovalReceipt, PatientMark, ScreenFrame, ScreenHeader, SectionTitle, StateMark, StatusPill, SystemStatus } from "./platform-ui";

const stages = [
  { label: "Access", value: "$4.2k", detail: "eligibility & estimates", icon: UserRoundCheck },
  { label: "Coding", value: "$12.8k", detail: "documentation support", icon: FileCheck2 },
  { label: "Authorization", value: "$8.6k", detail: "payer decisions", icon: ShieldCheck },
  { label: "Claims", value: "$38.4k", detail: "submitted & accepted", icon: ReceiptText },
  { label: "Remittance", value: "$16.9k", detail: "payer adjudication", icon: Landmark },
  { label: "Patient", value: "$6.5k", detail: "responsibility", icon: WalletCards },
];

const exceptions = [
  { id: "james", initials: "JW", patient: "James Walker", episode: "Evaluation + procedure", stop: "CO-97 denial", recommendation: "Add supported modifier 25 and resubmit", amount: "$350", due: "Appeal tomorrow", status: "risk" as const, stage: "Denials" },
  { id: "natalie", initials: "NW", patient: "Natalie Wong", episode: "Skyrizi authorization", stop: "Clinical attestation", recommendation: "Confirm dose after evidence review", amount: "$6,480", due: "Due 2:00 PM", status: "human" as const, stage: "Authorizations" },
  { id: "sarah", initials: "SM", patient: "Sarah Mitchell", episode: "Shave biopsy", stop: "Clinical plan dependency", recommendation: "Release estimate after biopsy approval", amount: "$395", due: "Before visit", status: "waiting" as const, stage: "Access" },
  { id: "alex", initials: "AR", patient: "Alex Rivera", episode: "Acne follow-up", stop: "Balance question", recommendation: "Approve source-grounded EOB explanation", amount: "$145", due: "Patient waiting 38m", status: "human" as const, stage: "Patient balances" },
  { id: "marcus", initials: "MB", patient: "Marcus Brooks", episode: "Excison", stop: "Coding support conflict", recommendation: "Choose documented lesion-size source", amount: "$820", due: "Today", status: "human" as const, stage: "Coding" },
  { id: "priya", initials: "PK", patient: "Priya Kumar", episode: "Payer payment", stop: "Unmatched ERA reference", recommendation: "Confirm allocation to claim lines", amount: "$640", due: "Today", status: "waiting" as const, stage: "Payments" },
];

const lenses = ["Horizons", "Access", "Authorizations", "Coding", "Claims", "Denials", "Patient balances", "Payments"];

export function RevenueScreen() {
  const [lens, setLens] = useState("Horizons");
  const [selectedId, setSelectedId] = useState("james");
  const [resolved, setResolved] = useState<Set<string>>(() => new Set());
  const visible = lens === "Horizons" ? exceptions : exceptions.filter((item) => item.stage === lens || (lens === "Claims" && item.id === "sarah"));
  const selected = exceptions.find((item) => item.id === selectedId) ?? visible[0] ?? exceptions[0];

  return <ScreenFrame>
    <ScreenHeader title="$87,420 is moving through 312 care journeys." description={`Ambrosia advanced 96 financial steps overnight. ${6 - resolved.size} need a person; clinicians see only work that requires clinical judgment or attestation.`} action={<SystemStatus label="Revenue operating normally" detail="$42,185 posted automatically" />} />
    <nav className="overflow-x-auto border-b border-[#dce3db] px-5 sm:px-8 lg:px-10" aria-label="Revenue views"><div className="mx-auto flex max-w-[1480px] min-w-max">{lenses.map((item) => <button type="button" key={item} onClick={() => setLens(item)} className={cn("border-b-2 px-4 py-4 text-xs", lens === item ? "border-[#1f5c43] font-semibold text-[#153f30]" : "border-transparent text-[#697a72] hover:text-[#214936]")}>{item}</button>)}</div></nav>
    <div className="mx-auto max-w-[1480px] px-5 py-7 sm:px-8 lg:px-10">
      <section><SectionTitle title="Revenue horizons" description="One financial arc from access to payment closure—always connected to the clinical source and patient explanation." />
        <div className="mt-4 grid overflow-hidden rounded-xl border border-[#d9dfd8] bg-white sm:grid-cols-2 xl:grid-cols-6">{stages.map((stage, index) => { const Icon = stage.icon; return <button type="button" key={stage.label} onClick={() => setLens(stage.label === "Authorization" ? "Authorizations" : stage.label === "Patient" ? "Patient balances" : stage.label)} className="relative border-b border-r border-[#e0e5df] p-4 text-left last:border-r-0 hover:bg-[#f6f8f4] sm:[&:nth-last-child(-n+2)]:border-b-0 xl:border-b-0"><div className="flex items-center gap-2"><span className="flex size-8 items-center justify-center rounded-full border border-[#aac0ae] bg-[#f3f7f2]"><Icon className="size-4 text-[#2b654b]" /></span><p className="text-xs font-semibold">{stage.label}</p></div><p className="mt-4 font-mono text-xl font-semibold">{stage.value}</p><p className="mt-1 text-[9px] text-[#6c7b73]">{stage.detail}</p>{index < stages.length - 1 ? <ChevronRight className="absolute right-2 top-1/2 hidden size-3 -translate-y-1/2 text-[#9aa79f] xl:block" /> : null}</button>; })}</div>
      </section>

      <div className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_420px]">
        <section className="min-w-0"><SectionTitle title={`${lens} · ${visible.filter((item) => !resolved.has(item.id)).length} exceptions`} description="Only items with a current action, ordered by deadline and financial or clinical risk." />
          <div className="mt-4 overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">
            <div className="hidden grid-cols-[minmax(180px,1fr)_130px_minmax(210px,1.2fr)_90px_110px_28px] gap-3 border-b border-[#e0e5df] bg-[#f5f7f3] px-4 py-3 text-[9px] font-semibold uppercase tracking-[0.12em] text-[#718078] md:grid"><span>Patient / episode</span><span>Stop</span><span>Recommended action</span><span>Amount</span><span>Deadline</span><span /></div>
            {visible.length ? visible.map((item) => <button type="button" key={item.id} onClick={() => setSelectedId(item.id)} className={cn("grid w-full gap-3 border-b border-[#e2e6e1] px-4 py-4 text-left last:border-b-0 md:grid-cols-[minmax(180px,1fr)_130px_minmax(210px,1.2fr)_90px_110px_28px] md:items-center", selected.id === item.id ? "bg-[#edf3eb] shadow-[inset_3px_0_0_#2b654b]" : "hover:bg-[#f7f8f4]", resolved.has(item.id) && "opacity-55")}><span className="flex items-center gap-3"><PatientMark initials={item.initials} size="sm" /><span><span className="block text-xs font-semibold">{item.patient}</span><span className="mt-1 block text-[9px] text-[#6b7a72]">{item.episode} · {item.stage}</span></span></span><span><StatusPill status={resolved.has(item.id) ? "complete" : item.status}>{resolved.has(item.id) ? "Released" : item.stop}</StatusPill></span><span className="text-[10px] leading-4 text-[#4e6157]">{item.recommendation}</span><span className="font-mono text-xs font-semibold">{item.amount}</span><span className="text-[10px] text-[#687870]">{item.due}</span><ChevronRight className="size-4 text-[#718078]" /></button>) : <div className="p-12 text-center text-xs text-[#6b7a72]">No active exceptions in this view.</div>}
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-3">{[["48 hours", "$31,280", "expected cash"], ["7 days", "$96,440", "payer & patient"], ["30 days", "$268,900", "modeled receipts"]].map(([horizon, value, detail]) => <div key={horizon} className="rounded-xl border border-[#d9dfd8] bg-white p-4"><p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[#718078]">{horizon}</p><p className="mt-3 font-mono text-2xl font-semibold">{value}</p><p className="mt-1 text-[10px] text-[#6b7a72]">{detail}</p></div>)}</div>
        </section>

        <aside className="overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">
          <header className="border-b border-[#e0e5df] p-5"><div className="flex items-start justify-between gap-3"><div className="flex items-center gap-3"><PatientMark initials={selected.initials} /><div><h2 className="text-sm font-semibold">{selected.patient}</h2><p className="mt-1 text-[10px] text-[#687870]">{selected.episode} · {selected.stage}</p></div></div><StatusPill status={resolved.has(selected.id) ? "complete" : selected.status}>{resolved.has(selected.id) ? "Released" : selected.stop}</StatusPill></div></header>
          <div className="space-y-5 p-5">
            {resolved.has(selected.id) ? <ApprovalReceipt><p className="font-semibold">Financial journey released.</p><p className="mt-1 text-xs">The correction, submission, payer monitor, and patient communication hold are now coordinated.</p></ApprovalReceipt> : null}
            <section><p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[#75827b]">Why Ambrosia stopped</p><p className="mt-2 text-xs leading-5 text-[#5b6c63]">{selected.id === "james" ? "The payer bundled the evaluation with the procedure. The signed note supports a separately identifiable service, but modifier attestation is consequential and requires billing approval." : selected.id === "natalie" ? "Payer criteria and prior treatment failures are assembled. The requested biologic dose still requires clinician attestation." : selected.id === "sarah" ? "The estimate is ready, but the clinical procedure plan is not yet authorized. Patient-facing cost communication remains staged." : selected.recommendation}</p></section>
            <section className="rounded-xl border border-[#d9dfd8] bg-[#f7f8f4] p-4"><div className="flex items-center gap-2"><Sparkles className="size-4 text-[#2b654b]" /><h3 className="text-xs font-semibold">Recommended action</h3></div><p className="mt-2 text-sm font-semibold leading-5">{selected.recommendation}</p><p className="mt-3 text-[10px] leading-4 text-[#6a7971]">Sources: signed note v3, payer response, claim edits, eligibility record · Policy v3.4.2</p></section>
            <section><p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[#75827b]">Approval releases</p><div className="mt-3 space-y-2">{["Apply sourced record update", "Submit through payer adapter", "Monitor acknowledgment and adjudication", "Keep patient statement suppressed until final", "Prepare plain-language patient update"].map((item) => <div key={item} className="flex items-center gap-3 text-[10px]"><StateMark status="moving" className="size-5" />{item}</div>)}</div></section>
            <section className="rounded-xl border border-[#d9dfd8] p-4"><div className="flex items-center gap-2"><Stethoscope className="size-4 text-[#2b654b]" /><p className="text-xs font-semibold">Clinical source connection</p></div><p className="mt-2 text-[10px] leading-5 text-[#63736a]">{selected.patient}’s financial work remains linked to the visit, signed documentation, procedure, result state, communication consent, and care closure.</p>{selected.id === "sarah" ? <Button asChild variant="outline" size="sm" className="mt-3"><Link href="/patients/sarah-mitchell">Open Sarah’s full journey</Link></Button> : null}</section>
            <section className="rounded-lg border border-[#d9dfd8] bg-[#f5f7f2] p-4"><div className="flex items-center gap-2"><ShieldCheck className="size-4 text-[#285e45]" /><p className="text-xs font-semibold">Permission boundary</p></div><p className="mt-2 text-[10px] leading-5 text-[#63736a]">Ambrosia may verify, assemble, validate, monitor, post matched remittances, and send approved updates. It stops for unsupported coding, clinical attestation, appeals, disputes, and policy-threshold refunds.</p></section>
            <Button disabled={resolved.has(selected.id) || selected.status === "waiting"} onClick={() => setResolved((current) => new Set(current).add(selected.id))} className="w-full bg-[#c76c00] text-white hover:bg-[#a95c00]"><RefreshCw className="size-4" />{resolved.has(selected.id) ? "Released" : selected.status === "waiting" ? "Waiting on dependency" : "Approve & release"}</Button>
          </div>
        </aside>
      </div>
    </div>
    <AgentDock context="revenue" />
  </ScreenFrame>;
}

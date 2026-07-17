"use client";

import { Beaker, Check, ChevronRight, Clock3, FileCheck2, MessageSquareText, Search, ShieldAlert, ShieldCheck, Stethoscope } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { AgentDock, ApprovalReceipt, PatientMark, ScreenFrame, ScreenHeader, SectionTitle, StatusPill } from "./platform-ui";

const results = [
  { id: "jordan", initials: "JL", patient: "Jordan Lee", test: "Skin, left nasal ala", diagnosis: "Nodular basal cell carcinoma", orderer: "Dr. Chen", state: "Provider review", due: "2h 18m", priority: "human" as const, notification: "Staged" },
  { id: "sarah", initials: "SM", patient: "Sarah Mitchell", test: "Left posterior shoulder", diagnosis: "Specimen expected Jul 20", orderer: "Dr. Chen", state: "Specimen monitor", due: "3d", priority: "moving" as const, notification: "Not ready" },
  { id: "mei", initials: "MT", patient: "Mei Thompson", test: "Right upper back", diagnosis: "Melanoma in situ", orderer: "Dr. Okafor", state: "Patient acknowledgment", due: "44m", priority: "risk" as const, notification: "Delivered" },
  { id: "natalie", initials: "NW", patient: "Natalie Wong", test: "CBC / CMP", diagnosis: "External lab pending", orderer: "Dr. Chen", state: "Waiting on lab", due: "Jul 20", priority: "waiting" as const, notification: "—" },
];

export function ResultsScreen() {
  const [selectedId, setSelectedId] = useState("jordan");
  const [closed, setClosed] = useState<Set<string>>(() => new Set());
  const selected = results.find((result) => result.id === selectedId) ?? results[0];

  return <ScreenFrame>
    <ScreenHeader title="Every result has an owner and an ending." description="Reading a result is not closure. Ambrosia keeps the loop open through review, disposition, patient notification, acknowledgment, and follow-up." action={<Button className="bg-[#c76c00] text-white hover:bg-[#a95c00]"><ShieldAlert className="size-4" />Review 4 results</Button>} />
    <section className="border-b border-[#dce3db] px-5 py-4 sm:px-8 lg:px-10"><div className="mx-auto grid max-w-[1480px] grid-cols-2 gap-3 sm:grid-cols-5">{[["37", "Open"], ["4", "Need provider review"], ["6", "Await acknowledgment"], ["1", "Overdue"], ["0", "Unmatched"]].map(([count, label], index) => <div key={label} className="rounded-lg border border-[#d9dfd8] bg-white p-3"><p className={cn("font-mono text-xl font-semibold", index === 3 && "text-[#a94435]")}>{count}</p><p className="mt-1 text-[10px] text-[#687870]">{label}</p></div>)}</div></section>
    <div className="mx-auto max-w-[1480px] px-5 py-7 sm:px-8 lg:px-10">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(390px,0.8fr)]">
        <section className="min-w-0"><div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between"><SectionTitle title="Unresolved result journeys" description="Ordered by clinical risk, deadline, and accountability." /><div className="relative"><Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-[#718078]" /><input className="h-9 rounded-lg border border-[#d5ded6] bg-white pl-9 pr-3 text-xs outline-none" placeholder="Search results" /></div></div>
          <div className="mt-4 overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">
            <div className="hidden grid-cols-[minmax(180px,1fr)_minmax(220px,1.3fr)_140px_130px_90px_28px] gap-3 border-b border-[#e0e5df] bg-[#f5f7f3] px-4 py-3 text-[9px] font-semibold uppercase tracking-[0.12em] text-[#718078] md:grid"><span>Patient / specimen</span><span>Result</span><span>State</span><span>Notification</span><span>SLA</span><span /></div>
            {results.map((result) => <button type="button" key={result.id} onClick={() => setSelectedId(result.id)} className={cn("grid w-full gap-3 border-b border-[#e2e6e1] px-4 py-4 text-left last:border-b-0 md:grid-cols-[minmax(180px,1fr)_minmax(220px,1.3fr)_140px_130px_90px_28px] md:items-center", selected.id === result.id ? "bg-[#edf3eb] shadow-[inset_3px_0_0_#2b654b]" : "hover:bg-[#f7f8f4]", closed.has(result.id) && "opacity-60")}><span className="flex items-center gap-3"><PatientMark initials={result.initials} size="sm" /><span><span className="block text-xs font-semibold">{result.patient}</span><span className="mt-1 block text-[9px] text-[#6b7a72]">{result.test} · {result.orderer}</span></span></span><span className="text-xs font-semibold leading-5">{result.diagnosis}</span><span><StatusPill status={closed.has(result.id) ? "complete" : result.priority}>{closed.has(result.id) ? "Closed" : result.state}</StatusPill></span><span className="text-[10px] text-[#5e7066]">{result.notification}</span><span className="font-mono text-[10px] text-[#5e7066]">{result.due}</span><ChevronRight className="size-4 text-[#718078]" /></button>)}
          </div>
        </section>

        <aside className="overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">
          <header className="border-b border-[#e0e5df] p-5"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-3"><PatientMark initials={selected.initials} /><div><h2 className="text-sm font-semibold">{selected.patient}</h2><p className="mt-1 text-[10px] text-[#687870]">{selected.test}</p></div></div><StatusPill status={closed.has(selected.id) ? "complete" : selected.priority}>{closed.has(selected.id) ? "Closed" : selected.state}</StatusPill></div></header>
          <div className="space-y-5 p-5">
            {closed.has(selected.id) ? <ApprovalReceipt><p className="font-semibold">Closure receipt recorded.</p><p className="mt-1 text-xs">Disposition, patient notification, follow-up, and accountability are linked to this result.</p></ApprovalReceipt> : null}
            <section><p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[#75827b]">Original pathology report</p><div className="mt-2 rounded-lg border border-[#dce2dc] bg-[#f8f8f4] p-4"><p className="text-sm font-semibold">{selected.diagnosis}</p><p className="mt-2 text-[10px] leading-5 text-[#63736a]">Source: Dermpath Labs · Accession DP-26-07149 · finalized Jul 17, 11:02 AM</p></div></section>
            <section><div className="flex items-center gap-2"><Beaker className="size-4 text-[#2b654b]" /><h3 className="text-xs font-semibold">Ambrosia summary</h3></div><p className="mt-2 text-xs leading-5 text-[#5b6c63]">{selected.id === "jordan" ? "Basal cell carcinoma requires treatment disposition. Mohs referral is supported by lesion location; patient explanation requires clinician review." : "The result journey is being monitored under the responsible clinician and lab SLA."}</p><button type="button" className="mt-2 text-[10px] font-semibold text-[#245942]">View report and provenance</button></section>
            <section className="rounded-lg border border-[#d9dfd8] p-4"><div className="flex items-center gap-2"><Stethoscope className="size-4 text-[#2b654b]" /><p className="text-xs font-semibold">Proposed disposition</p></div><p className="mt-2 text-xs leading-5">{selected.id === "jordan" ? "Refer for Mohs surgery; notify patient with approved explanation; schedule within two weeks." : "Continue assigned monitoring path and escalate at SLA."}</p></section>
            <section><p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[#75827b]">Closure contract</p><div className="mt-3 space-y-2">{[[FileCheck2, "Clinician review recorded"], [MessageSquareText, "Patient notification delivered"], [Check, "Acknowledgment or exception documented"], [Clock3, "Follow-up scheduled and monitored"]].map(([Icon, label]) => { const I = Icon as typeof Check; return <div key={String(label)} className="flex items-center gap-3 text-[10px]"><span className="flex size-6 items-center justify-center rounded-full border border-[#a7bbaa]"><I className="size-3.5 text-[#2b654b]" /></span>{label as string}</div>; })}</div></section>
            <div className="rounded-lg border border-[#d9dfd8] bg-[#f5f7f2] p-4"><div className="flex items-center gap-2"><ShieldCheck className="size-4 text-[#285e45]" /><p className="text-xs font-semibold">Accountability</p></div><p className="mt-2 text-[10px] leading-5 text-[#63736a]">Responsible clinician: Dr. Maya Chen · covering pool active · escalation in {selected.due}.</p></div>
            <Button disabled={closed.has(selected.id) || selected.priority === "waiting" || selected.priority === "moving"} onClick={() => setClosed((current) => new Set(current).add(selected.id))} className="w-full bg-[#c76c00] text-white hover:bg-[#a95c00]">{closed.has(selected.id) ? "Closure recorded" : "Approve disposition & release"}</Button>
          </div>
        </aside>
      </div>
    </div>
    <AgentDock />
  </ScreenFrame>;
}

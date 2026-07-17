"use client";

import { CalendarCheck2, Check, ChevronRight, CircleDollarSign, Clock3, FileText, MessageSquareText, ShieldCheck, Upload } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

import { ApprovalReceipt, CareRail, ScreenFrame, StatusPill } from "./platform-ui";

const patientSteps = [
  { label: "Information", detail: "Complete", meta: "Jul 13", status: "complete" as const },
  { label: "Plan review", detail: "With your clinician", meta: "Today", status: "human" as const },
  { label: "Visit", detail: "Mon, Jul 20", meta: "8:30 AM", status: "moving" as const },
  { label: "Lab result", detail: "After your visit", meta: "2–3 business days", status: "moving" as const },
  { label: "Follow-up", detail: "We’ll contact you", meta: "Portal + SMS", status: "moving" as const },
  { label: "Skin check", detail: "Planned", meta: "Aug 17", status: "moving" as const },
];

export function PatientPlanScreen() {
  const [confirmed, setConfirmed] = useState(false);
  return <ScreenFrame className="bg-[#eef5ed] pb-12">
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
      <header className="rounded-2xl border border-[#d4dfd4] bg-[#fffefa] p-6 shadow-[0_18px_50px_rgba(22,65,47,0.05)] sm:p-8"><div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between"><div><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#61746b]">Sarah’s care plan</p><h1 className="mt-2 text-3xl font-semibold tracking-[-0.045em] text-[#103b2b] sm:text-4xl">Your care plan is moving.</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-[#5c6d65]">Your care team is reviewing the biopsy plan. Everything else—your visit, lab tracking, updates, estimate, and follow-up—is prepared.</p></div><StatusPill status="human">One step to review</StatusPill></div><div className="mt-7 overflow-x-auto pb-2"><CareRail steps={patientSteps} /></div></header>

      {confirmed ? <div className="mt-5"><ApprovalReceipt><p className="font-semibold">Visit confirmed for Monday, Jul 20 at 8:30 AM.</p><p className="mt-1 text-xs">We’ll text you a reminder and keep this plan updated.</p></ApprovalReceipt></div> : null}

      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <main className="space-y-5">
          <section className="rounded-2xl border border-[#d4dfd4] bg-[#fffefa] p-6"><div className="flex items-start gap-4"><span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-[#fff1d8]"><CalendarCheck2 className="size-5 text-[#a75b00]" /></span><div className="min-w-0 flex-1"><p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#a75b00]">Next for you</p><h2 className="mt-1 text-lg font-semibold">Confirm Monday’s visit</h2><p className="mt-2 text-xs leading-5 text-[#617169]">Jul 20 · 8:30 AM · Midtown Dermatology · Room 2</p><div className="mt-4 flex flex-wrap gap-2"><Button disabled={confirmed} onClick={() => setConfirmed(true)} className="bg-[#1d563e] text-white hover:bg-[#164630]"><Check className="size-4" />{confirmed ? "Confirmed" : "Confirm visit"}</Button><Button variant="outline">Ask to reschedule</Button></div></div></div></section>
          <section className="rounded-2xl border border-[#d4dfd4] bg-[#fffefa] p-6"><div className="flex items-center justify-between"><h2 className="text-base font-semibold">Your messages</h2><Button variant="ghost" size="sm">View all <ChevronRight className="size-3.5" /></Button></div><div className="mt-4 flex gap-3 rounded-xl bg-[#f4f7f1] p-4"><MessageSquareText className="mt-0.5 size-5 shrink-0 text-[#2b654b]" /><div><p className="text-xs font-semibold">You asked: “Will this leave a big scar?”</p><p className="mt-2 text-xs leading-5 text-[#617169]">Your dermatologist is reviewing the exact plan and will answer before the procedure. You can decide after your questions are answered.</p><p className="mt-2 text-[9px] text-[#7a8780]">Care team · reply in progress</p></div></div><Button variant="outline" className="mt-4 w-full">Ask another question</Button></section>
          <section className="rounded-2xl border border-[#d4dfd4] bg-[#fffefa] p-6"><h2 className="text-base font-semibold">What happens after the visit</h2><div className="mt-4 grid gap-3 sm:grid-cols-2">{[[FileText, "Aftercare", "Simple wound-care steps will appear here."], [Clock3, "Lab tracking", "We’ll track your result and keep you updated."], [MessageSquareText, "Result explanation", "Your dermatologist reviews it before you’re notified."], [ShieldCheck, "Follow-up", "No result closes until your next step is clear."]].map(([Icon, title, detail]) => { const I = Icon as typeof FileText; return <div key={String(title)} className="rounded-xl border border-[#e0e5df] p-4"><I className="size-4 text-[#2b654b]" /><p className="mt-3 text-xs font-semibold">{title as string}</p><p className="mt-1 text-[10px] leading-4 text-[#687870]">{detail as string}</p></div>; })}</div></section>
        </main>
        <aside className="space-y-5">
          <section className="rounded-2xl border border-[#d4dfd4] bg-[#fffefa] p-6"><div className="flex items-center gap-2"><CircleDollarSign className="size-5 text-[#2b654b]" /><h2 className="text-base font-semibold">Cost estimate</h2></div><p className="mt-4 font-mono text-3xl font-semibold">$85</p><p className="mt-1 text-xs text-[#687870]">your estimated responsibility</p><div className="mt-4 space-y-2 border-t border-[#e1e6e1] pt-4 text-xs"><div className="flex justify-between"><span className="text-[#687870]">Estimated charge</span><span>$395</span></div><div className="flex justify-between"><span className="text-[#687870]">Expected insurance</span><span>$310</span></div></div><button type="button" className="mt-4 text-[10px] font-semibold text-[#245942]">How this estimate works</button></section>
          <section className="rounded-2xl border border-[#d4dfd4] bg-[#fffefa] p-6"><div className="flex items-center gap-2"><Upload className="size-5 text-[#2b654b]" /><h2 className="text-base font-semibold">Your records</h2></div><p className="mt-3 text-xs leading-5 text-[#617169]">Your lesion photos and intake are safely attached to this care plan.</p><Button variant="outline" className="mt-4 w-full">Add a photo or document</Button></section>
          <section className="rounded-2xl border border-[#d4dfd4] bg-[#fffefa] p-6"><div className="flex items-center gap-2"><ShieldCheck className="size-5 text-[#2b654b]" /><h2 className="text-base font-semibold">You stay in control</h2></div><p className="mt-3 text-xs leading-5 text-[#617169]">Change communication preferences, review consent, ask for a person, or question a charge at any time.</p><Button variant="ghost" className="mt-2 px-0 text-[#245942]">Manage preferences <ChevronRight className="size-3.5" /></Button></section>
        </aside>
      </div>
    </div>
  </ScreenFrame>;
}

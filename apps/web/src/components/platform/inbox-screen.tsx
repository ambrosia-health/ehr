"use client";

import {
  CheckCircle2,
  ChevronDown,
  Clock3,
  MessageSquareText,
  Phone,
  Search,
  Send,
  ShieldCheck,
  Smartphone,
  Sparkles,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import { AgentDock, PatientMark, ScreenFrame, ScreenHeader, SectionTitle, StatusPill } from "./platform-ui";

const queue = [
  { id: "natalie", initials: "NW", patient: "Natalie Wong", episode: "Psoriasis flare", preview: "The redness is spreading and feels warm.", stop: "Safety language detected", due: "8m", status: "risk" as const, owner: "Clinician" },
  { id: "sarah", initials: "SM", patient: "Sarah Mitchell", episode: "Changing lesion", preview: "Will this leave a big scar?", stop: "Clinical explanation approval", due: "22m", status: "human" as const, owner: "Dr. Chen" },
  { id: "jordan", initials: "JL", patient: "Jordan Lee", episode: "Mohs closure", preview: "Wound check request remains unread.", stop: "Delivery fallback choice", due: "2h", status: "waiting" as const, owner: "Ambrosia" },
  { id: "benjamin", initials: "BC", patient: "Benjamin Carter", episode: "Patient balance", preview: "$65 reminder paused.", stop: "Financial email consent expired", due: "Today", status: "waiting" as const, owner: "Ambrosia" },
];

const threads: Record<string, { messages: { actor: string; body: string; time: string; kind: "patient" | "team" | "activity" }[]; draft: string; why: string; release: string }> = {
  natalie: { messages: [{ actor: "Natalie", body: "The redness is spreading and feels warm. Is that normal?", time: "9:42 AM", kind: "patient" }, { actor: "Ambrosia", body: "Safety language detected. Routine automation paused and a clinical task opened with an 8-minute SLA.", time: "9:42 AM", kind: "activity" }], draft: "Thanks for letting us know. A clinician is reviewing this now. If you develop fever, rapidly spreading redness, severe pain, or feel unwell, seek urgent care.", why: "Acknowledgment only; no diagnosis or treatment advice. Grounded in the approved escalation policy.", release: "Send portal acknowledgment, notify Natalie by SMS, and keep the urgent clinical monitor open." },
  sarah: { messages: [{ actor: "Sarah", body: "Will this leave a big scar?", time: "9:31 AM", kind: "patient" }, { actor: "Ambrosia", body: "Question matched to the proposed biopsy plan and approved aftercare policy. A response is staged for clinical approval.", time: "9:31 AM", kind: "activity" }], draft: "A shave biopsy usually leaves a small, flat mark that fades over time. We’ll review the exact site and expected healing with you before the procedure, and you can decide after your questions are answered.", why: "Uses Sarah’s proposed procedure, lesion location, and approved biopsy aftercare. The plan is not yet authorized, so Ambrosia cannot send this independently.", release: "Send via secure portal, notify by consented SMS, and start a 24-hour response monitor." },
  jordan: { messages: [{ actor: "Ambrosia", body: "Please upload a clear photo of the wound in good light.", time: "Yesterday", kind: "team" }, { actor: "Ambrosia", body: "Portal message delivered but unread for 48 hours. SMS is disabled by preference.", time: "8:05 AM", kind: "activity" }], draft: "Hi Jordan, we’re checking that you received your wound-photo request. Please call us if the portal is difficult to access.", why: "The approved Mohs closure program permits automated phone outreach when secure messages remain unread for 48 hours.", release: "Place policy-approved phone outreach and defer the wound-check deadline by one business day." },
  benjamin: { messages: [{ actor: "Ambrosia", body: "A $65 adjudicated balance is ready for explanation. Email delivery paused because consent expired.", time: "8:12 AM", kind: "activity" }], draft: "Your insurance has finished processing your recent visit. A remaining balance of $65 is now available in your secure portal, with the explanation from your EOB.", why: "Grounded in the adjudicated EOB and financial communication policy. No clinical content is included.", release: "Deliver through the secure portal only and open a consent renewal request." },
};

export function InboxScreen() {
  const [selectedId, setSelectedId] = useState("sarah");
  const [draft, setDraft] = useState(threads.sarah.draft);
  const [sent, setSent] = useState<Set<string>>(() => new Set());
  const selected = queue.find((item) => item.id === selectedId) ?? queue[0];
  const thread = threads[selected.id];

  function choose(id: string) {
    setSelectedId(id);
    setDraft(threads[id].draft);
  }

  return <ScreenFrame>
    <ScreenHeader title="284 conversations are moving." description={`${queue.length - sent.size} need clinical or policy judgment. Ambrosia is advancing 246 routine conversations without an administrative queue.`} action={<div className="flex flex-wrap gap-2"><StatusPill status="human">3 clinician</StatusPill><StatusPill status="waiting">6 policy exceptions</StatusPill><Button variant="outline">Programs <ChevronDown className="size-4" /></Button></div>} />
    <section className="border-b border-[#dce3db] px-5 py-4 sm:px-8 lg:px-10"><div className="mx-auto grid max-w-[1480px] grid-cols-2 gap-3 sm:grid-cols-5">{[["3", "Needs clinician", "human"], ["6", "Policy exceptions", "human"], ["2", "Delivery issue", "risk"], ["27", "Waiting on patient", "waiting"], ["246", "Advancing", "complete"]].map(([count, label, status]) => <button type="button" key={label} className="rounded-lg border border-[#d9dfd8] bg-white p-3 text-left hover:border-[#bfcbbf]"><p className="font-mono text-xl font-semibold">{count}</p><p className="mt-1 text-[10px] text-[#687870]">{label}</p><span className="sr-only">{status}</span></button>)}</div></section>

    <div className="mx-auto grid max-w-[1480px] xl:grid-cols-[310px_minmax(0,1fr)_330px]">
      <aside className="border-b border-[#dce3db] xl:min-h-[720px] xl:border-b-0 xl:border-r">
        <div className="border-b border-[#e0e5df] p-4"><div className="relative"><Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-[#718078]" /><input className="h-9 w-full rounded-lg border border-[#d5ded6] bg-white pl-9 pr-3 text-xs outline-none focus:border-[#6c9a80]" placeholder="Search patient, episode, or intent" /></div><div className="mt-3 flex gap-2"><button type="button" className="rounded-full bg-[#e8efe7] px-3 py-1 text-[9px] font-semibold text-[#24523c]">Approval stops</button><button type="button" className="rounded-full border border-[#d7ded7] px-3 py-1 text-[9px] text-[#66766d]">All conversations</button></div></div>
        <div>{queue.map((item) => <button key={item.id} type="button" onClick={() => choose(item.id)} className={cn("flex w-full gap-3 border-b border-[#e2e6e1] p-4 text-left", selected.id === item.id ? "bg-[#edf3eb] shadow-[inset_3px_0_0_#2b654b]" : "hover:bg-[#f7f8f4]", sent.has(item.id) && "opacity-55")}><PatientMark initials={item.initials} size="sm" /><span className="min-w-0 flex-1"><span className="flex items-center justify-between"><span className="text-xs font-semibold">{item.patient}</span><span className="font-mono text-[9px] text-[#718078]">{item.due}</span></span><span className="mt-1 block text-[10px] text-[#5d6e65]">{item.episode}</span><span className="mt-2 block truncate text-[10px] text-[#6f7e76]">{item.preview}</span><span className="mt-2 flex items-center justify-between"><StatusPill status={sent.has(item.id) ? "complete" : item.status}>{sent.has(item.id) ? "Released" : item.stop}</StatusPill><span className="text-[9px] text-[#7a8780]">{item.owner}</span></span></span></button>)}</div>
      </aside>

      <main className="flex min-w-0 flex-col border-b border-[#dce3db] xl:min-h-[720px] xl:border-b-0 xl:border-r">
        <header className="flex items-center justify-between border-b border-[#e0e5df] p-4"><div className="flex items-center gap-3"><PatientMark initials={selected.initials} /><div><h2 className="text-sm font-semibold">{selected.episode}</h2><p className="mt-1 text-[10px] text-[#687870]">{selected.patient} · Visit-linked secure thread</p></div></div><Button asChild variant="outline" size="sm"><Link href={selected.id === "sarah" ? "/patients/sarah-mitchell" : "/patients"}>Open patient</Link></Button></header>
        <div className="flex-1 bg-[#f8f8f3] p-5 sm:p-7"><div className="mx-auto max-w-2xl space-y-4">{thread.messages.map((message, index) => message.kind === "activity" ? <div key={`${message.time}-${index}`} className="flex items-start gap-3 rounded-lg border border-[#d9e1d9] bg-[#eef3ed] p-3"><Sparkles className="mt-0.5 size-4 shrink-0 text-[#2b654b]" /><div><p className="text-[10px] font-semibold text-[#315442]">{message.actor} completed routine work</p><p className="mt-1 text-[10px] leading-4 text-[#64746b]">{message.body}</p><p className="mt-1 text-[9px] text-[#849087]">{message.time} · Policy v3.4.2</p></div></div> : <div key={`${message.time}-${index}`} className={cn("flex", message.kind === "patient" ? "justify-start" : "justify-end")}><div className={cn("max-w-[82%] rounded-xl border p-4 text-xs leading-5", message.kind === "patient" ? "bg-white" : "border-[#2b654b] bg-[#245b43] text-white")}><p>{message.body}</p><p className={cn("mt-2 text-[9px]", message.kind === "patient" ? "text-[#7a8780]" : "text-white/65")}>{message.actor} · {message.time} · Secure portal</p></div></div>)}{sent.has(selected.id) ? <div className="flex justify-end"><div className="max-w-[82%] rounded-xl border border-[#bcd5c4] bg-[#eef7f0] p-4"><div className="flex items-center gap-2 text-xs font-semibold text-[#214d38]"><CheckCircle2 className="size-4" />Approved and delivered</div><p className="mt-2 text-xs leading-5 text-[#486558]">{draft}</p><p className="mt-2 text-[9px] text-[#6b7d73]">Secure portal · delivered just now · SMS notification queued</p></div></div> : null}</div></div>
        <div className="border-t border-[#dce3db] bg-white p-4"><div className="mx-auto max-w-2xl"><div className="mb-3 rounded-lg border border-[#d5e0d7] bg-[#f2f6f1] p-3"><div className="flex items-center justify-between gap-3"><span className="flex items-center gap-2 text-xs font-semibold"><Sparkles className="size-4 text-[#2b654b]" />Grounded response ready</span><span className="text-[9px] text-[#6e7d75]">Requires {selected.owner.toLowerCase()} approval</span></div><p className="mt-2 text-[10px] leading-4 text-[#66766d]"><strong>Why this response:</strong> {thread.why}</p></div><Textarea value={draft} onChange={(event) => setDraft(event.target.value)} className="min-h-24 resize-none border-[#d4ddd5] text-xs leading-5" aria-label={`Reply to ${selected.patient}`} /><div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3 text-[9px] text-[#6c7b73]"><span className="flex items-center gap-1"><ShieldCheck className="size-3.5" />Policy checked</span><span className="flex items-center gap-1"><Smartphone className="size-3.5" />Portal + SMS</span></div><Button disabled={sent.has(selected.id)} onClick={() => setSent((current) => new Set(current).add(selected.id))} className="bg-[#1d563e] text-white hover:bg-[#164630]"><Send className="size-4" />{sent.has(selected.id) ? "Delivered" : "Approve & send"}</Button></div></div></div>
      </main>

      <aside className="p-5 xl:min-h-[720px]"><SectionTitle title="Patient-agent context" description="The minimum clinical, financial, consent, and monitoring context for this conversation." />
        <div className="mt-5 space-y-5">
          <section><p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[#75827b]">Current goal</p><p className="mt-2 text-xs font-semibold leading-5">{selected.id === "sarah" ? "Resolve changing lesion through safe pathology closure" : selected.episode}</p></section>
          <section className="border-t border-[#e0e5df] pt-4"><p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[#75827b]">Active monitor</p><div className="mt-3 flex items-start gap-3"><Clock3 className="mt-0.5 size-4 text-[#bb6500]" /><div><p className="text-xs font-semibold">{selected.stop}</p><p className="mt-1 text-[10px] text-[#6b7a72]">Due {selected.due} · owned by {selected.owner}</p></div></div></section>
          <section className="border-t border-[#e0e5df] pt-4"><p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[#75827b]">Approval releases</p><p className="mt-2 text-[10px] leading-5 text-[#5c6e64]">{thread.release}</p></section>
          <section className="border-t border-[#e0e5df] pt-4"><p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[#75827b]">Consent & channels</p><div className="mt-3 space-y-2">{[[MessageSquareText, "Secure portal", "Active"], [Smartphone, "SMS notifications", selected.id === "jordan" ? "Disabled" : "Verified"], [Phone, "Phone outreach", "Policy controlled"]].map(([Icon, label, value]) => { const I = Icon as typeof Phone; return <div key={String(label)} className="flex items-center gap-2 text-[10px]"><I className="size-3.5 text-[#2b654b]" /><span className="flex-1">{label as string}</span><span className="font-semibold">{value as string}</span></div>; })}</div></section>
          <section className="rounded-xl border border-[#d9dfd8] bg-white p-4"><div className="flex items-center gap-2"><UserRoundCheck className="size-4 text-[#2b654b]" /><p className="text-xs font-semibold">Communication authority</p></div><p className="mt-2 text-[10px] leading-5 text-[#66766d]">May send approved reminders and signed instructions. Must stop for new symptoms, clinical explanations, missing consent, disputes, or content outside policy.</p></section>
        </div>
      </aside>
    </div>
    <AgentDock />
  </ScreenFrame>;
}

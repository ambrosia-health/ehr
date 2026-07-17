"use client";

import {
  Activity,
  Beaker,
  Check,
  ClipboardCheck,
  CreditCard,
  FileText,
  HeartPulse,
  History,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  Stethoscope,
} from "lucide-react";
import Image from "next/image";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { sarahSteps } from "./platform-fixtures";
import { AgentDock, ApprovalReceipt, CareRail, ScreenFrame, StatusPill } from "./platform-ui";

const memories = [
  { icon: Activity, title: "Lesion change over 4 months", detail: "7 × 5 mm; color variation and widening", source: "Patient photos · Jul 13" },
  { icon: HeartPulse, title: "Family history", detail: "Melanoma in mother (age 57)", source: "Intake · Jul 13" },
  { icon: ShieldCheck, title: "Personal history", detail: "Atypical nevus (2023)", source: "Prior records · Apr 2026" },
  { icon: Beaker, title: "Pathology SLA", detail: "Hudson Community Lab · 2–3 business days", source: "Lab contract · Jul 16" },
  { icon: MessageSquareText, title: "Unread patient question", detail: "“Will this leave a big scar?”", source: "Inbox · Jul 16" },
];

export function PatientAgentScreen() {
  const [reviewOpen, setReviewOpen] = useState(false);
  const [approved, setApproved] = useState(false);
  const steps = approved ? sarahSteps.map((step, index) => index === 3 ? { ...step, detail: "Biopsy plan approved", meta: "Dr. Chen · just now", status: "complete" as const } : index > 3 ? { ...step, status: "moving" as const } : step) : sarahSteps;

  return (
    <ScreenFrame>
      <header className="border-b border-[#dce3db] px-5 py-7 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-[1480px] flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
          <div className="flex min-w-0 items-start gap-5">
            <Image src="/images/patients/sarah-mitchell.png" alt="Sarah Mitchell" width={112} height={112} priority className="size-24 rounded-full border-4 border-white object-cover shadow-[0_0_0_1px_#cfd8d0] sm:size-28" />
            <div className="pt-1"><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#6b7a72]">Patient care agent</p><h1 className="mt-1 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">Sarah Mitchell</h1><p className="mt-2 text-xs text-[#65756c]">38 y · she/her · MRN AM-10482</p><p className="mt-4 max-w-2xl text-base font-medium leading-6">Resolve changing lesion through safe pathology closure.</p><div className="mt-3 flex flex-wrap items-center gap-2"><StatusPill status={approved ? "complete" : "moving"}>{approved ? "Plan approved" : "Care agent active"}</StatusPill><span className="text-[10px] text-[#6b7a72]">8 completed · {approved ? 0 : 1} decision waiting · 6 downstream actions {approved ? "advancing" : "staged"}</span></div></div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2"><Button variant="outline"><FileText className="size-4" />Open chart</Button><Button onClick={() => setReviewOpen(true)} disabled={approved} className="bg-[#c76c00] text-white hover:bg-[#a95c00]"><Stethoscope className="size-4" />{approved ? "Biopsy plan approved" : "Review biopsy plan"}</Button></div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1480px] xl:grid-cols-[minmax(0,1fr)_330px]">
        <main className="min-w-0 border-[#dce3db] xl:border-r">
          <section className="px-5 py-7 sm:px-8 lg:px-10">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-lg font-semibold tracking-[-0.025em]">Sarah’s care arc</h2><p className="mt-1 text-xs text-[#6c7b73]">Jul 13 – Aug 17, 2026 · clinical, communication, and financial work in one journey</p></div><div className="flex gap-4 text-[9px] text-[#6c7b73]"><span>● Completed</span><span className="text-[#bd6700]">◯ Waiting for you</span><span>○ Staged</span></div></div>
            {approved ? <div className="mt-5"><ApprovalReceipt><p className="font-semibold">Six downstream actions released.</p><p className="mt-1 text-xs">Procedure plan, pathology order, aftercare, specimen monitor, estimate, and claim draft are now advancing.</p></ApprovalReceipt></div> : null}
            <div className="mt-7 overflow-x-auto pb-3"><CareRail steps={steps} compact /></div>
          </section>

          <Tabs defaultValue="journey" className="gap-0 border-t border-[#dce3db]">
            <TabsList variant="line" className="h-12 w-full justify-start gap-6 overflow-x-auto rounded-none border-b border-[#dce3db] bg-transparent px-5 sm:px-8 lg:px-10">
              {[["journey", "Journey"], ["chart", "Chart"], ["lesions", "Lesions"], ["results", "Results"], ["messages", "Messages"], ["financial", "Financial"], ["audit", "Audit"]].map(([value, label]) => <TabsTrigger key={value} value={value} className="h-12 px-0 text-xs">{label}</TabsTrigger>)}
            </TabsList>
            <TabsContent value="journey" className="m-0 px-5 py-7 sm:px-8 lg:px-10">
              <div className="grid gap-8 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
                <section><h3 className="text-sm font-semibold">Why Ambrosia stopped</h3><p className="mt-3 text-sm leading-6 text-[#53655b]">The lesion has changed in size and color over four months. Combined with Sarah’s history of an atypical nevus and family history of melanoma, tissue diagnosis is the safest next step. Ambrosia can prepare that plan but cannot choose or authorize it.</p><div className="mt-6 rounded-xl border border-[#d9dfd8] bg-white p-5"><p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#6b7a72]">Recommended plan</p><p className="mt-2 text-sm font-semibold">Shave biopsy in-office on Jul 20</p><ul className="mt-3 space-y-2 text-xs text-[#586960]"><li>Single site · left posterior shoulder</li><li>Local anesthesia · low-risk procedure</li><li>Send specimen to Hudson Community Lab</li></ul><div className="mt-4 flex justify-between border-t border-[#e1e6e1] pt-3 text-[10px] text-[#6b7a72]"><span>Confidence 91%</span><button type="button" className="font-semibold text-[#245942]">View evidence & rationale</button></div></div></section>
                <section><h3 className="text-sm font-semibold">Recent activity</h3><div className="mt-3 overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">{[
                  ["Previsit synthesis completed", "Ambrosia", "Jul 14 · 10:45 AM"],
                  ["Pathology order draft prepared", "Ambrosia", "Jul 17 · 11:02 AM"],
                  ["Visit scheduled", "Ambrosia", "Jul 20 · 8:30 AM"],
                  ["Patient message received", "Sarah", "Jul 16 · 9:31 AM"],
                  ["Coverage verified", "Availity", "Jul 13 · 8:49 AM"],
                ].map(([title, actor, time]) => <div key={title} className="flex items-center gap-3 border-b border-[#e5e9e4] p-3 last:border-b-0"><span className="flex size-5 items-center justify-center rounded-full border border-[#91ae9b]"><Check className="size-3 text-[#275e43]" /></span><p className="min-w-0 flex-1 text-xs font-semibold">{title} <span className="font-normal text-[#77857d]">{actor}</span></p><span className="text-[9px] text-[#718078]">{time}</span></div>)}</div></section>
              </div>
            </TabsContent>
            <TabsContent value="chart" className="m-0 px-5 py-7 sm:px-8 lg:px-10"><DetailPanel icon={ClipboardCheck} title="Clinical chart" description="Allergies, medications, problem list, signed records, and structured observations remain attached to their source and freshness." items={["Adhesive tape allergy · active", "Sertraline · current medication", "Family history of melanoma", "Atypical nevus · 2023", "No anticoagulant use recorded"]} /></TabsContent>
            <TabsContent value="lesions" className="m-0 px-5 py-7 sm:px-8 lg:px-10"><div className="grid gap-5 md:grid-cols-[260px_1fr]"><Image src="/images/clinical/sarah-left-posterior-shoulder.png" alt="Sarah Mitchell left posterior shoulder lesion" width={520} height={390} className="aspect-[4/3] w-full rounded-xl border object-cover" /><DetailPanel icon={Activity} title="Left posterior shoulder" description="7 × 5 mm asymmetric macule with an irregular, focally notched border and variegated tan–dark brown pigmentation." items={["Change: darkened and widened over ~4 months", "Symptoms: occasional itch; no bleeding or pain", "Comparison: patient-provided photos", "Latest observation: Jul 16 · Dr. Maya Chen"]} /></div></TabsContent>
            <TabsContent value="results" className="m-0 px-5 py-7 sm:px-8 lg:px-10"><DetailPanel icon={Beaker} title="Diagnostic closure plan" description="A pathology monitor will open when the specimen is recorded. Reading alone will not close the result." items={["Responsible clinician: Dr. Maya Chen", "Lab SLA: 2–3 business days", "Provider review required", "Patient notification and acknowledgment required", "Surveillance disposition required"]} /></TabsContent>
            <TabsContent value="messages" className="m-0 px-5 py-7 sm:px-8 lg:px-10"><DetailPanel icon={MessageSquareText} title="Patient communication" description="Sarah asked: “Will this leave a big scar?” Ambrosia staged a response from the proposed plan and approved aftercare policy." items={["Portal active · SMS verified", "English · quiet hours 9 PM–8 AM", "Clinical answer requires approval", "Approval starts a 24-hour response monitor"]} /></TabsContent>
            <TabsContent value="financial" className="m-0 px-5 py-7 sm:px-8 lg:px-10"><DetailPanel icon={CreditCard} title="Financial journey" description="Blue Horizon PPO is active. Sarah will see a plain-language estimate only after the clinical plan is approved." items={["No prior authorization required", "$395 estimated charge", "$310 expected plan payment", "$85 estimated patient responsibility", "Claim draft remains staged until note signature"]} /></TabsContent>
            <TabsContent value="audit" className="m-0 px-5 py-7 sm:px-8 lg:px-10"><DetailPanel icon={History} title="Agent audit" description="Every action is append-only, source-linked, policy-versioned, and reviewable." items={["46 source reads", "8 completed actions", "1 clinical stop", "Policy v3.4.2", "100% activity coverage"]} /></TabsContent>
          </Tabs>
        </main>

        <aside className="px-5 py-7 sm:px-8 xl:px-6">
          <h2 className="text-sm font-semibold">Agent memory & monitors</h2><p className="mt-1 text-[10px] text-[#6b7a72]">Only facts relevant to this goal, with source and freshness.</p>
          <div className="mt-5">{memories.map((memory) => { const Icon = memory.icon; return <div key={memory.title} className="flex gap-3 border-b border-[#e0e5df] py-4 first:pt-0"><Icon className="mt-0.5 size-5 shrink-0 text-[#285f46]" /><div><p className="text-xs font-semibold">{memory.title}</p><p className="mt-1 text-[11px] leading-4 text-[#52645a]">{memory.detail}</p><p className="mt-2 text-[9px] text-[#77857e]">Source: {memory.source} · Fresh</p></div></div>; })}</div>
          <div className="mt-6 rounded-xl border border-[#d9dfd8] bg-white p-4"><h3 className="text-xs font-semibold">Agent permissions</h3><p className="mt-2 text-[10px] leading-5 text-[#63736a]">May prepare, reconcile, coordinate, and monitor. Must stop before diagnosis, treatment choice, signature, prescribing, or clinical result notification.</p><button type="button" className="mt-3 text-[10px] font-semibold text-[#245942]">View policy v3.4.2</button></div>
        </aside>
      </div>

      <Sheet open={reviewOpen} onOpenChange={setReviewOpen}>
        <SheetContent className="w-full overflow-y-auto bg-[#fffefa] p-0 sm:max-w-[560px]">
          <SheetHeader className="border-b border-[#dce3db] p-6 text-left"><SheetTitle>Review biopsy plan</SheetTitle><SheetDescription>One clinical decision releases six coordinated steps across the patient journey.</SheetDescription></SheetHeader>
          <div className="space-y-5 p-6">
            <div className="rounded-xl border border-[#d9dfd8] bg-white p-5"><div className="flex items-center gap-2"><Sparkles className="size-4 text-[#286047]" /><h3 className="text-sm font-semibold">Prepared recommendation</h3></div><p className="mt-3 text-sm font-semibold">Shave biopsy · left posterior shoulder</p><p className="mt-2 text-xs leading-5 text-[#5d6e65]">Single-site procedure under local anesthesia, specimen to Hudson Community Lab, result closure monitored for 2–3 business days.</p></div>
            <div><h3 className="text-sm font-semibold">Approval releases</h3><div className="mt-3 space-y-2">{["Procedure plan", "Pathology order", "Approved aftercare", "Specimen and result monitor", "Patient estimate", "Evidence-linked claim draft"].map((item) => <div key={item} className="flex items-center gap-3 rounded-lg border border-[#e1e6e1] bg-white px-3 py-2.5 text-xs"><span className="flex size-5 items-center justify-center rounded-full border border-[#9bb5a4]"><Check className="size-3 text-[#286047]" /></span>{item}</div>)}</div></div>
            <div className="rounded-lg border border-[#d9dfd8] bg-[#f5f7f2] p-4"><div className="flex items-center gap-2"><ShieldCheck className="size-4 text-[#285e45]" /><p className="text-xs font-semibold">You remain the clinical authorizer</p></div><p className="mt-2 text-[10px] leading-5 text-[#63736a]">Approval records the exact recommendation, evidence set, policy, source versions, and your identity. The note still requires signature after the encounter.</p></div>
            <div className="flex gap-2"><Button variant="outline" className="flex-1">Edit recommendation</Button><Button className="flex-1 bg-[#c76c00] text-white hover:bg-[#a95c00]" onClick={() => { setApproved(true); setReviewOpen(false); }}><Stethoscope className="size-4" />Approve & release</Button></div>
          </div>
        </SheetContent>
      </Sheet>
      <AgentDock context="Sarah" />
    </ScreenFrame>
  );
}

function DetailPanel({ icon: Icon, title, description, items }: { icon: typeof Activity; title: string; description: string; items: string[] }) {
  return <section className="rounded-xl border border-[#d9dfd8] bg-white p-5"><div className="flex items-center gap-3"><span className="flex size-9 items-center justify-center rounded-lg bg-[#e8efe7]"><Icon className="size-4 text-[#285f46]" /></span><div><h2 className="text-sm font-semibold">{title}</h2><p className="mt-1 text-xs leading-5 text-[#63736a]">{description}</p></div></div><div className="mt-5 grid gap-2 sm:grid-cols-2">{items.map((item) => <div key={item} className="flex items-start gap-2 rounded-lg bg-[#f6f8f4] p-3 text-xs leading-5"><Check className="mt-0.5 size-3.5 shrink-0 text-[#286047]" />{item}</div>)}</div></section>;
}

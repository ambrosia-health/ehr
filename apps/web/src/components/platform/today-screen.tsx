"use client";

import {
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Eye,
  FileCheck2,
  MessageSquareText,
  PencilLine,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

import { attentionItems, type AttentionItem } from "./platform-fixtures";

const visits = [
  { time: "8:30 AM", patient: "Sarah Mitchell", reason: "Changing lesion", state: "Needs review", href: "/patients/sarah-mitchell" },
  { time: "9:15 AM", patient: "Alex Rivera", reason: "Psoriasis follow-up", state: "Ready", href: "/patients" },
  { time: "10:00 AM", patient: "Priya Shah", reason: "Acne program", state: "Ready", href: "/patients" },
] as const;

interface DecisionDetail {
  summary: string;
  explanation: string;
  plan: string;
  planDetail: string;
  signals: Array<{ title: string; detail: string }>;
  receipt: string;
}

const decisionDetails: Record<string, DecisionDetail> = {
  "sarah-biopsy": {
    summary: "This lesion changed since her last visit.",
    explanation: "Ambrosia paused the routine follow-up because the new photo and message suggest she should be seen sooner.",
    plan: "Convert today’s visit to urgent dermoscopy",
    planDetail: "Keep the 8:30 slot, prepare consent and the dermoscopy template, and hold biopsy supplies only if the exam confirms concern.",
    signals: [
      { title: "Visible change", detail: "The new photo differs from the baseline captured seven months ago." },
      { title: "Patient concern", detail: "Sarah describes recent darkening and a rough edge." },
      { title: "Timing mismatch", detail: "The routine plan would otherwise wait another four weeks." },
    ],
    receipt: "Slot protected · chart summarized · supplies checked · patient update drafted",
  },
  "jordan-pathology": {
    summary: "Jordan’s pathology needs a clinical disposition.",
    explanation: "The final report confirms nodular basal cell carcinoma. Ambrosia prepared the referral path but cannot choose or explain treatment.",
    plan: "Confirm Mohs referral and patient explanation",
    planDetail: "Release the referral, open scheduling outreach, and send the reviewed explanation through the secure portal.",
    signals: [
      { title: "Final diagnosis", detail: "Dermpath finalized nodular basal cell carcinoma at 11:02 AM." },
      { title: "Closure required", detail: "A result is not closed until disposition, notification, and follow-up are documented." },
      { title: "SLA approaching", detail: "The clinician review window closes in two hours." },
    ],
    receipt: "Report reconciled · referral drafted · explanation prepared · SLA monitor open",
  },
  "natalie-symptoms": {
    summary: "Natalie reported a new safety symptom.",
    explanation: "New joint pain sits outside the routine psoriasis check-in policy, so the automated response stopped before offering clinical advice.",
    plan: "Choose a same-day triage disposition",
    planDetail: "Review symptom severity, confirm the safest response, and release the acknowledgment plus any needed lab or visit coordination.",
    signals: [
      { title: "New symptom", detail: "Joint pain was not present in the previous biologic monitoring check-in." },
      { title: "Treatment context", detail: "The symptom may change the current monitoring plan." },
      { title: "Patient waiting", detail: "Natalie has been waiting for a reviewed response for 47 minutes." },
    ],
    receipt: "Message classified · chart context gathered · acknowledgment drafted · monitor open",
  },
};

export function TodayScreen() {
  const [resolved, setResolved] = useState<Set<string>>(() => new Set());
  const [showEvidence, setShowEvidence] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [editedPlans, setEditedPlans] = useState<Record<string, string>>({});
  const [lastApproved, setLastApproved] = useState<string | null>(null);

  const openItems = useMemo(() => attentionItems.filter((item) => !resolved.has(item.id)), [resolved]);
  const current = openItems[0] ?? null;
  const detail = current ? decisionDetails[current.id] : null;
  const estimatedMinutes = Math.max(0, openItems.length * 2 + (openItems.length > 1 ? 2 : 0));

  function approve(item: AttentionItem) {
    setResolved((currentResolved) => new Set(currentResolved).add(item.id));
    setLastApproved(item.patient);
    setShowEvidence(false);
    setEditOpen(false);
  }

  function openEditor() {
    if (!current || !detail) return;
    setDraft(editedPlans[current.id] ?? detail.plan);
    setEditOpen(true);
  }

  function saveDraft() {
    if (!current || !draft.trim()) return;
    setEditedPlans((plans) => ({ ...plans, [current.id]: draft.trim() }));
    setEditOpen(false);
  }

  return (
    <main className="min-h-[calc(100vh-4.5rem)] bg-background px-4 py-7 text-foreground sm:px-7 lg:px-10 lg:py-9">
      <div className="mx-auto max-w-[1120px]">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-primary">Friday, July 17</p>
            <h1 className="mt-1.5 text-[28px] font-semibold tracking-[-0.035em] text-foreground sm:text-[32px]">Good morning, Maya.</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">Clinical judgment first. Ambrosia is coordinating everything around it.</p>
          </div>
          <div className="flex items-center gap-3 border-l-2 border-decision pl-3 text-sm sm:text-right">
            <CalendarDays className="size-4 text-decision" aria-hidden="true" />
            <div>
              <p className="font-medium text-foreground">Clinic starts at 8:30 AM</p>
              <p className="mt-0.5 text-xs text-muted-foreground">10 visits · all charts prepared</p>
            </div>
          </div>
        </header>

        {lastApproved ? (
          <div role="status" className="mt-5 flex items-center gap-2.5 border border-primary/20 bg-secondary px-4 py-3 text-xs text-secondary-foreground">
            <CheckCircle2 className="size-4 shrink-0 text-primary" aria-hidden="true" />
            {lastApproved}’s approved plan is moving. The next decision is ready.
          </div>
        ) : null}

        <section className="mt-7 overflow-hidden rounded-lg border border-border bg-card" aria-labelledby="decision-worklist-title">
          <div className="flex flex-col gap-2 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <h2 id="decision-worklist-title" className="text-sm font-semibold text-foreground">Clinical decisions</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">Only work that requires your judgment appears here.</p>
            </div>
            <p className="text-xs font-medium text-decision">{openItems.length} {openItems.length === 1 ? "decision" : "decisions"} · about {estimatedMinutes} min</p>
          </div>

          {current && detail ? (
            <article aria-labelledby="current-decision">
              <div className="grid lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.9fr)_210px]">
                <div className="px-5 py-6 sm:px-6 lg:border-r lg:border-border">
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">Decision {resolved.size + 1} of {attentionItems.length}</p>
                    <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"><Clock3 className="size-3.5" aria-hidden="true" />About 2 min</span>
                  </div>
                  <div className="mt-5 flex items-center gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-border bg-muted text-[11px] font-semibold text-foreground">{current.initials}</span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-foreground">{current.patient}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">{current.episode} · {current.due}</p>
                    </div>
                  </div>
                  <h3 id="current-decision" className="mt-5 max-w-2xl text-[24px] font-semibold leading-[1.2] tracking-[-0.035em] text-foreground">{detail.summary}</h3>
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">{detail.explanation}</p>
                </div>

                <div className="border-t border-border bg-muted/45 px-5 py-6 sm:px-6 lg:border-t-0 lg:border-r">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">Recommended plan</p>
                  <h3 className="mt-3 text-lg font-semibold leading-snug tracking-[-0.02em] text-foreground">{editedPlans[current.id] ?? detail.plan}</h3>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{detail.planDetail}</p>
                  <div className="mt-5 flex items-center gap-3 border-t border-border pt-4">
                    <ShieldCheck className="size-5 text-[#167681]" aria-hidden="true" />
                    <div><p className="text-xl font-semibold tracking-[-0.03em] text-[#116d78]">{current.confidence}%</p><p className="text-[10px] text-muted-foreground">confidence</p></div>
                  </div>
                </div>

                <div className="border-t border-border px-5 py-6 lg:border-t-0">
                  <div className="flex items-start gap-2 text-decision">
                    <Clock3 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                    <div><p className="text-xs font-semibold">Review before visit</p><p className="mt-0.5 text-[11px] text-muted-foreground">{current.due}</p></div>
                  </div>
                  <div className="mt-5 grid gap-2">
                    <Button className="h-11 rounded-md bg-primary px-4 text-primary-foreground shadow-none hover:bg-primary/90" onClick={() => approve(current)}>
                      <Check className="size-4" />Approve plan
                    </Button>
                    <Button variant="outline" className="h-11 rounded-md shadow-none" onClick={openEditor}><PencilLine className="size-4" />Modify</Button>
                    <Button variant="ghost" className="h-9 rounded-md text-xs" aria-expanded={showEvidence} onClick={() => setShowEvidence((visible) => !visible)}>
                      <Eye className="size-3.5" />{showEvidence ? "Hide evidence" : "View evidence"}
                    </Button>
                  </div>
                </div>
              </div>

              <div className="border-t border-border">
                <div className="grid divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
                  {detail.signals.map((signal) => (
                    <div key={signal.title} className="px-5 py-4">
                      <p className="text-xs font-semibold text-foreground">{signal.title}</p>
                      <p className="mt-1 text-[11px] leading-5 text-muted-foreground">{signal.detail}</p>
                    </div>
                  ))}
                </div>
                {showEvidence ? (
                  <div role="region" aria-label="Evidence summary" className="border-t border-border bg-secondary/60 px-5 py-4 text-xs leading-5 text-secondary-foreground sm:px-6">
                    Recommendation uses the photo delta, patient message, lesion history, active medications, and today’s available visit slot. Policy version 3.4.2; evidence is linked in the chart.
                  </div>
                ) : null}
                <div className="flex items-start gap-2 border-t border-border px-5 py-3 text-[11px] text-muted-foreground sm:px-6">
                  <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-[#167681]" aria-hidden="true" />
                  <span><strong className="font-semibold text-foreground">Already handled:</strong> {detail.receipt}</span>
                </div>
              </div>
            </article>
          ) : (
            <div className="px-6 py-12 text-center">
              <span className="mx-auto flex size-10 items-center justify-center rounded-full bg-secondary text-primary"><Check className="size-5" /></span>
              <h2 className="mt-4 text-lg font-semibold">All decisions are clear.</h2>
              <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">Ambrosia released the approved work and will interrupt you only when new clinical judgment is required.</p>
            </div>
          )}
        </section>

        <section className="mt-7 overflow-hidden rounded-lg border border-border bg-card" aria-labelledby="today-schedule-title">
          <div className="flex items-center justify-between border-b border-border px-5 py-4 sm:px-6">
            <div>
              <h2 id="today-schedule-title" className="text-sm font-semibold">Today’s clinic</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">First visits; seven more are ready.</p>
            </div>
            <Link href="/patients" className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline">View patients <ChevronRight className="size-3.5" /></Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[650px] text-left text-xs">
              <thead className="bg-muted/60 text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                <tr><th className="px-6 py-2.5">Time</th><th className="px-4 py-2.5">Patient</th><th className="px-4 py-2.5">Visit</th><th className="px-6 py-2.5 text-right">Preparation</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {visits.map((visit, index) => (
                  <tr key={`${visit.time}-${visit.patient}`} className="transition-colors hover:bg-muted/35">
                    <td className="px-6 py-3.5 font-medium text-foreground">{visit.time}</td>
                    <td className="px-4 py-3.5"><Link className="font-semibold text-foreground hover:text-primary hover:underline" href={visit.href}>{visit.patient}</Link></td>
                    <td className="px-4 py-3.5 text-muted-foreground">{visit.reason}</td>
                    <td className={index === 0 ? "px-6 py-3.5 text-right font-medium text-decision" : "px-6 py-3.5 text-right font-medium text-[#167681]"}>{visit.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-7 border-y border-border py-4" aria-label="Automation status">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="text-xs font-semibold text-foreground">Everything else is moving</p><p className="mt-1 text-[11px] text-muted-foreground">No operational exceptions need your attention.</p></div>
            <div className="grid grid-cols-2 gap-x-5 gap-y-2 text-[11px] text-muted-foreground sm:flex sm:flex-wrap">
              <span className="inline-flex items-center gap-1.5"><CalendarDays className="size-3.5 text-primary" />42 journeys</span>
              <span className="inline-flex items-center gap-1.5"><FileCheck2 className="size-3.5 text-primary" />6 results filed</span>
              <span className="inline-flex items-center gap-1.5"><MessageSquareText className="size-3.5 text-primary" />9 updates sent</span>
              <span className="inline-flex items-center gap-1.5"><ShieldCheck className="size-3.5 text-[#167681]" />0 safety risks</span>
            </div>
          </div>
        </section>
      </div>

      <Sheet open={editOpen} onOpenChange={setEditOpen}>
        <SheetContent className="w-full overflow-y-auto border-l border-border bg-card p-0 sm:max-w-[520px]">
          <SheetHeader className="border-b border-border p-6 text-left">
            <SheetTitle>Edit recommendation</SheetTitle>
            <SheetDescription>Adjust the clinical wording before approving the coordinated plan.</SheetDescription>
          </SheetHeader>
          <div className="space-y-5 p-6">
            <label htmlFor="recommendation" className="text-xs font-semibold">Recommendation</label>
            <Textarea id="recommendation" value={draft} onChange={(event) => setDraft(event.target.value)} className="min-h-32 rounded-md" />
            <div className="border border-border bg-muted p-4 text-xs leading-5 text-muted-foreground">
              Ambrosia will recalculate downstream patient, pathology, scheduling, and revenue steps after you save.
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1 rounded-md" onClick={() => setEditOpen(false)}>Cancel</Button>
              <Button className="flex-1 rounded-md" onClick={saveDraft} disabled={!draft.trim()}>Save recommendation</Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </main>
  );
}

"use client";

import {
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Eye,
  FileCheck2,
  LoaderCircle,
  MessageSquareText,
  PencilLine,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

import { completeEncounter, updateAssessmentPlan } from "./product-actions";
import { clinicianFirstName, formatWorkspaceDate } from "./product-workspace";
import { useProductWorkspace } from "./product-workspace-provider";

export function TodayScreen() {
  const { workspace, refresh } = useProductWorkspace();
  const [showEvidence, setShowEvidence] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [draft, setDraft] = useState(workspace.encounter.draftNote.assessmentPlan);
  const [busy, setBusy] = useState<"approve" | "modify" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const completed = Boolean(workspace.encounter.completionReceipt || workspace.encounter.note.signedAt);
  const decisionCount = completed ? 0 : 1;
  const firstVisit = workspace.schedule[0] ?? null;
  const openQueueCount = workspace.queues.reduce((sum, queue) => sum + queue.count, 0);
  const unreadMessages = workspace.queues.find((queue) => queue.id === "messages")?.count ?? 0;
  const pathologyCount = workspace.queues.find((queue) => queue.id === "path")?.count ?? 0;

  async function approve() {
    setBusy("approve");
    setError(null);
    try {
      await completeEncounter(workspace);
      await refresh();
      setNotice(`${workspace.patient.name}’s approved plan is moving.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The plan could not be approved.");
    } finally {
      setBusy(null);
    }
  }

  function openEditor() {
    setDraft(workspace.encounter.draftNote.assessmentPlan);
    setEditOpen(true);
  }

  async function saveDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.trim()) return;
    setBusy("modify");
    setError(null);
    try {
      await updateAssessmentPlan(workspace, draft.trim());
      await refresh();
      setEditOpen(false);
      setNotice(`${workspace.patient.name}’s recommendation was saved to the chart.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The recommendation could not be saved.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="min-h-[calc(100vh-4.5rem)] bg-background px-4 py-7 text-foreground sm:px-7 lg:px-10 lg:py-9">
      <div className="mx-auto max-w-[1120px]">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-primary">
              {formatWorkspaceDate(workspace.scenario.currentTime, workspace, { weekday: "long", month: "long", day: "numeric" })}
            </p>
            <h1 className="mt-1.5 text-[28px] font-semibold tracking-[-0.035em] sm:text-[32px]">Good morning, {clinicianFirstName(workspace)}.</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">Clinical judgment first. Ambrosia is coordinating everything around it.</p>
          </div>
          <div className="flex items-center gap-3 border-l-2 border-decision pl-3 text-sm sm:text-right">
            <CalendarDays className="size-4 text-decision" aria-hidden="true" />
            <div>
              <p className="font-medium">{firstVisit ? `Clinic starts at ${firstVisit.time}` : "No visits scheduled"}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{workspace.schedule.length} scheduled · {workspace.commandCenter.summariesPrepared} {workspace.commandCenter.summariesPrepared === 1 ? "summary" : "summaries"} prepared</p>
            </div>
          </div>
        </header>

        {notice ? <div role="status" className="mt-5 flex items-center gap-2.5 border border-primary/20 bg-secondary px-4 py-3 text-xs text-secondary-foreground"><CheckCircle2 className="size-4 shrink-0 text-primary" />{notice}</div> : null}
        {error ? <div role="alert" className="mt-5 border border-destructive/25 bg-destructive/5 px-4 py-3 text-xs text-destructive">{error}</div> : null}

        <section className="mt-7 overflow-hidden rounded-lg border border-border bg-card" aria-labelledby="decision-worklist-title">
          <div className="flex flex-col gap-2 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <h2 id="decision-worklist-title" className="text-sm font-semibold">Clinical decisions</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">Only work that requires your judgment appears here.</p>
            </div>
            <p className="text-xs font-medium text-decision">{decisionCount} {decisionCount === 1 ? "decision" : "decisions"}</p>
          </div>

          {!completed ? (
            <article aria-labelledby="current-decision">
              <div className="grid lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.9fr)_210px]">
                <div className="px-5 py-6 sm:px-6 lg:border-r lg:border-border">
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">Decision 1 of 1</p>
                    <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"><Clock3 className="size-3.5" />Focused review</span>
                  </div>
                  <div className="mt-5 flex items-center gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-border bg-muted text-[11px] font-semibold">{workspace.patient.initials}</span>
                    <div><p className="text-sm font-semibold">{workspace.patient.name}</p><p className="mt-0.5 text-xs text-muted-foreground">{workspace.patient.lesion.label} · {firstVisit?.status ?? workspace.patient.readinessStatus}</p></div>
                  </div>
                  <h3 id="current-decision" className="mt-5 max-w-2xl text-[24px] font-semibold leading-[1.2] tracking-[-0.035em]">Biopsy this changing lesion?</h3>
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">{workspace.encounter.previsitSummary}</p>
                </div>

                <div className="border-t border-border bg-muted/45 px-5 py-6 sm:px-6 lg:border-r lg:border-t-0">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">Recommended plan</p>
                  <h3 className="mt-3 text-lg font-semibold leading-snug tracking-[-0.02em]">{workspace.encounter.draftNote.assessmentPlan}</h3>
                  <p className="mt-3 text-xs leading-5 text-muted-foreground">{workspace.encounter.proposals.length} durable actions are prepared and remain blocked until approval.</p>
                  <div className="mt-5 flex items-center gap-3 border-t border-border pt-4"><ShieldCheck className="size-5 text-[#167681]" /><div><p className="text-xs font-semibold text-[#116d78]">Evidence linked</p><p className="text-[10px] text-muted-foreground">Source records retained</p></div></div>
                </div>

                <div className="border-t border-border px-5 py-6 lg:border-t-0">
                  <div className="flex items-start gap-2 text-decision"><Clock3 className="mt-0.5 size-4 shrink-0" /><div><p className="text-xs font-semibold">Review before visit</p><p className="mt-0.5 text-[11px] text-muted-foreground">{firstVisit?.time ?? "No deadline"}</p></div></div>
                  <div className="mt-5 grid gap-2">
                    <Button className="h-11 rounded-md" onClick={approve} disabled={busy !== null || workspace.encounter.proposals.length === 0}>{busy === "approve" ? <LoaderCircle className="size-4 animate-spin" /> : <Check className="size-4" />}Approve plan</Button>
                    <Button variant="outline" className="h-11 rounded-md shadow-none" onClick={openEditor} disabled={busy !== null}><PencilLine className="size-4" />Modify</Button>
                    <Button variant="ghost" className="h-9 rounded-md text-xs" aria-expanded={showEvidence} onClick={() => setShowEvidence((visible) => !visible)}><Eye className="size-3.5" />{showEvidence ? "Hide evidence" : "View evidence"}</Button>
                  </div>
                </div>
              </div>

              <div className="border-t border-border">
                <div className="grid divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
                  <div className="px-5 py-4"><p className="text-xs font-semibold">Observed change</p><p className="mt-1 text-[11px] leading-5 text-muted-foreground">{workspace.patient.lesion.change}</p></div>
                  <div className="px-5 py-4"><p className="text-xs font-semibold">Exam evidence</p><p className="mt-1 text-[11px] leading-5 text-muted-foreground">{workspace.patient.lesion.dimensions} · {workspace.patient.lesion.border} · {workspace.patient.lesion.pigmentation}</p></div>
                  <div className="px-5 py-4"><p className="text-xs font-semibold">Symptoms</p><p className="mt-1 text-[11px] leading-5 text-muted-foreground">{workspace.patient.lesion.symptoms.join("; ") || "None recorded"}</p></div>
                </div>
                {showEvidence ? <div role="region" aria-label="Evidence summary" className="border-t border-border bg-secondary/60 px-5 py-4 text-xs leading-5 text-secondary-foreground sm:px-6">{workspace.patient.lesion.latestObservation.comparison || workspace.patient.lesion.latestObservation.assessment || workspace.encounter.draftNote.focusedExam}</div> : null}
                <div className="flex items-start gap-2 border-t border-border px-5 py-3 text-[11px] text-muted-foreground sm:px-6"><CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-[#167681]" /><span><strong className="font-semibold text-foreground">Already prepared:</strong> {workspace.encounter.proposals.map((proposal) => proposal.title).join(" · ")}</span></div>
              </div>
            </article>
          ) : (
            <div className="px-6 py-12 text-center"><span className="mx-auto flex size-10 items-center justify-center rounded-full bg-secondary text-primary"><Check className="size-5" /></span><h2 className="mt-4 text-lg font-semibold">All decisions are clear.</h2><p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">The signed encounter and released actions are recorded in the database.</p></div>
          )}
        </section>

        <section className="mt-7 overflow-hidden rounded-lg border border-border bg-card" aria-labelledby="today-schedule-title">
          <div className="flex items-center justify-between border-b border-border px-5 py-4 sm:px-6"><div><h2 id="today-schedule-title" className="text-sm font-semibold">Today’s clinic</h2><p className="mt-0.5 text-xs text-muted-foreground">{workspace.commandCenter.readinessPercent}% ready across the current schedule.</p></div><Link href="/patients" className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline">View patients <ChevronRight className="size-3.5" /></Link></div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[650px] text-left text-xs"><thead className="bg-muted/60 text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground"><tr><th className="px-6 py-2.5">Time</th><th className="px-4 py-2.5">Patient</th><th className="px-4 py-2.5">Visit</th><th className="px-6 py-2.5 text-right">Preparation</th></tr></thead>
              <tbody className="divide-y divide-border">{workspace.schedule.map((visit) => <tr key={visit.id} className="hover:bg-muted/35"><td className="px-6 py-3.5 font-medium">{visit.time}</td><td className="px-4 py-3.5"><Link className="font-semibold hover:text-primary hover:underline" href={visit.patient === workspace.patient.name ? `/patients/${workspace.patient.id}` : "/patients"}>{visit.patient}</Link></td><td className="px-4 py-3.5 text-muted-foreground">{visit.visit}</td><td className="px-6 py-3.5 text-right font-medium text-[#167681]">{visit.readinessStatus}</td></tr>)}</tbody>
            </table>
          </div>
        </section>

        <section className="mt-7 border-y border-border py-4" aria-label="Automation status"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-xs font-semibold">Everything else is moving</p><p className="mt-1 text-[11px] text-muted-foreground">{openQueueCount} queued items remain visible in durable work queues.</p></div><div className="grid grid-cols-2 gap-x-5 gap-y-2 text-[11px] text-muted-foreground sm:flex sm:flex-wrap"><span className="inline-flex items-center gap-1.5"><CalendarDays className="size-3.5 text-primary" />{workspace.schedule.length} visits</span><span className="inline-flex items-center gap-1.5"><FileCheck2 className="size-3.5 text-primary" />{pathologyCount} pathology</span><span className="inline-flex items-center gap-1.5"><MessageSquareText className="size-3.5 text-primary" />{unreadMessages} messages</span><span className="inline-flex items-center gap-1.5"><ShieldCheck className="size-3.5 text-[#167681]" />{workspace.commandCenter.documentationSupportPercent}% documented</span></div></div></section>
      </div>

      <Sheet open={editOpen} onOpenChange={setEditOpen}>
        <SheetContent className="w-full overflow-y-auto border-l border-border bg-card p-0 sm:max-w-[520px]">
          <SheetHeader className="border-b border-border p-6 text-left"><SheetTitle>Edit recommendation</SheetTitle><SheetDescription>The saved change creates a new durable note version before approval.</SheetDescription></SheetHeader>
          <form onSubmit={saveDraft} className="space-y-5 p-6"><label htmlFor="recommendation" className="text-xs font-semibold">Recommendation</label><Textarea id="recommendation" value={draft} onChange={(event) => setDraft(event.target.value)} className="min-h-32 rounded-md" /><div className="flex gap-2"><Button type="button" variant="outline" className="flex-1 rounded-md" onClick={() => setEditOpen(false)}>Cancel</Button><Button type="submit" className="flex-1 rounded-md" disabled={!draft.trim() || busy !== null}>{busy === "modify" ? <LoaderCircle className="size-4 animate-spin" /> : null}Save recommendation</Button></div></form>
        </SheetContent>
      </Sheet>
    </main>
  );
}

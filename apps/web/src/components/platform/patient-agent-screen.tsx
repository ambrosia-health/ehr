"use client";

import {
  ArrowRight,
  Beaker,
  CalendarDays,
  Check,
  ClipboardCheck,
  ClipboardList,
  Clock3,
  FileText,
  LoaderCircle,
  MessageSquareText,
  ShieldCheck,
  TrendingUp,
  UsersRound,
} from "lucide-react";
import Image from "next/image";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

import { completeEncounter, updateAssessmentPlan } from "./product-actions";
import { formatWorkspaceDate } from "./product-workspace";
import { useProductWorkspace } from "./product-workspace-provider";
import { ScreenFrame } from "./platform-ui";

export function PatientAgentScreen({ patientId }: { patientId: string }) {
  const { workspace, refresh } = useProductWorkspace();
  const [modifyOpen, setModifyOpen] = useState(false);
  const [draftRecommendation, setDraftRecommendation] = useState(workspace.encounter.draftNote.assessmentPlan);
  const [busy, setBusy] = useState<"approve" | "modify" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const approved = Boolean(workspace.encounter.completionReceipt || workspace.encounter.note.signedAt);
  const lesion = workspace.patient.lesion;
  const appointment = workspace.intake?.bookedAppointment;
  const sarahConversation = workspace.conversations.find((conversation) => conversation.patientId === workspace.patient.id);
  const lastMessage = sarahConversation?.messages.at(-1);
  const procedureProposal = workspace.encounter.proposals.find((proposal) => proposal.category === "Procedure") ?? workspace.encounter.proposals[0];

  if (workspace.patient.id !== patientId) {
    return <main className="mx-auto max-w-xl px-6 py-16"><h1 className="text-xl font-semibold">Patient not available</h1><p className="mt-2 text-sm text-muted-foreground">This patient is not included in your authorized workspace.</p></main>;
  }

  function changeModifyOpen(open: boolean) {
    if (open) setDraftRecommendation(workspace.encounter.draftNote.assessmentPlan);
    setModifyOpen(open);
  }

  async function approve() {
    setBusy("approve");
    setError(null);
    try {
      await completeEncounter(workspace);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The encounter could not be released.");
    } finally {
      setBusy(null);
    }
  }

  async function saveRecommendation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const recommendation = draftRecommendation.trim();
    if (!recommendation) return;
    setBusy("modify");
    setError(null);
    try {
      await updateAssessmentPlan(workspace, recommendation);
      await refresh();
      setModifyOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The recommendation could not be saved.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <ScreenFrame className="bg-[#f7f8f7] px-3 py-5 sm:px-6 sm:py-8">
      <main className="mx-auto max-w-[1080px] overflow-hidden rounded-lg border border-[#d9dfe5] bg-white text-[#172033]">
        <header className="flex min-h-24 flex-col gap-4 border-b border-[#dde2e8] px-5 py-4 sm:px-6 md:flex-row md:items-center md:justify-between">
          <div className="flex min-w-0 items-center gap-4"><span className="flex size-16 shrink-0 items-center justify-center rounded-full border border-[#d9dfe5] bg-[#eff5ff] text-sm font-semibold text-[#174f91]">{workspace.patient.initials}</span><div className="min-w-0"><h1 className="truncate text-2xl font-semibold tracking-[-0.035em] text-[#111827]">{workspace.patient.name}</h1><p className="mt-1 text-sm text-[#667085]">{workspace.patient.age} y · {workspace.patient.pronouns} · {workspace.patient.mrn}</p></div></div>
          <div className="flex items-start gap-3 text-sm text-[#344054] md:max-w-[300px]"><CalendarDays className="mt-0.5 size-4 shrink-0" /><p><span className="font-medium">{appointment ? `Visit planned: ${formatWorkspaceDate(appointment.startsAt, workspace, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" })}` : "No visit scheduled"}</span><span className="mt-0.5 block text-xs text-[#7b8495]">{workspace.patient.readinessStatus}</span></p></div>
        </header>

        <section aria-labelledby="decision-title" className="px-5 pb-4 pt-5 sm:px-6">
          {error ? <div role="alert" className="mb-4 border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">{error}</div> : null}
          <div className="grid items-stretch gap-5 lg:grid-cols-[minmax(290px,1.05fr)_minmax(350px,1fr)_190px]">
            <div className="py-2"><p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#0f5cc4]">Clinical decision</p><h2 id="decision-title" className="mt-3 text-[clamp(1.75rem,2.45vw,2rem)] font-semibold leading-[1.08] tracking-[-0.045em] text-[#111827]">Biopsy this {lesion.label.toLowerCase()}?</h2><p className="mt-4 text-sm text-[#667085]">{lesion.location} · observed {formatWorkspaceDate(lesion.latestObservation.observedAt, workspace, { month: "short", day: "numeric" })}</p></div>

            <section aria-labelledby="recommended-plan-title" className="grid min-h-[136px] rounded-md bg-[#f7f7f5] p-4 sm:grid-cols-[minmax(0,1fr)_110px]"><div className="sm:pr-4"><p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#0f5cc4]">Recommended plan</p><h3 id="recommended-plan-title" className="mt-3 text-xl font-semibold tracking-[-0.025em] text-[#111827]">{procedureProposal?.title ?? "Prepared plan"}</h3><p className="mt-1.5 text-[11px] leading-[18px] text-[#475467]">{workspace.encounter.draftNote.assessmentPlan}</p></div><div className="mt-4 flex items-center gap-3 border-t border-[#dfe3e7] pt-4 sm:mt-7 sm:block sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0 sm:text-center"><div className="flex items-center justify-center gap-2 text-[#167a83]"><ShieldCheck className="size-6 shrink-0" /><span className="text-sm font-semibold">Linked</span></div><p className="mt-1 text-xs text-[#667085]">evidence</p></div></section>

            <div className="flex flex-col justify-between gap-3"><div aria-live="polite" className={approved ? "text-[#167a83]" : "text-[#b85e00]"}><div className="flex items-start gap-2">{approved ? <Check className="mt-0.5 size-4 shrink-0" /> : <Clock3 className="mt-0.5 size-4 shrink-0" />}<p className="text-[11px] font-semibold">{approved ? `Released ${formatWorkspaceDate(workspace.encounter.note.signedAt!, workspace, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}` : "Awaiting clinician review"}</p></div><p className="ml-6 mt-1 text-xs text-[#667085]">{approved ? `${workspace.encounter.proposals.length} actions advancing` : `${workspace.encounter.proposals.length} prepared actions`}</p></div><div className="grid gap-2.5"><Button type="button" size="lg" disabled={approved || busy !== null} onClick={approve} className="h-11 rounded-md bg-[#0f5cc4] text-sm font-medium text-white hover:bg-[#0b4ea9]">{busy === "approve" ? <LoaderCircle className="size-4 animate-spin" /> : approved ? <Check className="size-4" /> : null}{approved ? "Approved & released" : "Approve & release"}</Button><Button type="button" size="lg" variant="outline" disabled={approved || busy !== null} aria-expanded={modifyOpen} aria-controls="modify-biopsy-plan" onClick={() => changeModifyOpen(true)} className="h-11 rounded-md border-[#9ca6b5] bg-white text-sm font-medium text-[#172033] shadow-none">Modify</Button></div></div>
          </div>

          <div className="mt-4 grid gap-2.5 md:grid-cols-2">
            <figure className="overflow-hidden rounded-md border border-[#d9dfe5] bg-[#fafafa]"><figcaption className="flex h-9 items-center justify-between gap-3 border-b border-[#d9dfe5] px-3 text-xs text-[#667085]"><span className="font-medium text-[#344054]">Clinical photo</span><span>{formatWorkspaceDate(lesion.overviewImage.capturedAt, workspace, { month: "short", day: "numeric" })} · {lesion.dimensions}</span></figcaption><Image src={lesion.overviewImage.url} alt={`Clinical photograph of ${workspace.patient.name}'s ${lesion.location.toLowerCase()} lesion`} width={1120} height={510} priority sizes="(min-width: 1280px) 540px, (min-width: 768px) 45vw, 100vw" className="aspect-[2.3/1] w-full object-cover object-[center_72%]" /></figure>
            <figure className="overflow-hidden rounded-md border border-[#d9dfe5] bg-[#fafafa]"><figcaption className="flex h-9 items-center justify-between gap-3 border-b border-[#d9dfe5] px-3 text-xs text-[#667085]"><span className="font-medium text-[#344054]">Dermoscopy</span><span>{formatWorkspaceDate(lesion.dermoscopyImage.capturedAt, workspace, { month: "short", day: "numeric" })} · {lesion.dermoscopyImage.name}</span></figcaption><Image src={lesion.dermoscopyImage.url} alt={`Dermoscopy image of ${workspace.patient.name}'s ${lesion.location.toLowerCase()} lesion`} width={1120} height={510} priority sizes="(min-width: 1280px) 540px, (min-width: 768px) 45vw, 100vw" className="aspect-[2.3/1] w-full scale-[1.6] bg-black object-contain" /></figure>
          </div>

          <section aria-labelledby="key-evidence-title" className="mt-4"><h3 id="key-evidence-title" className="mb-2 text-base font-semibold tracking-[-0.02em]">Key evidence</h3><div className="overflow-x-auto rounded-md border border-[#d9dfe5]"><table className="w-full min-w-[800px] table-fixed border-collapse text-left text-xs leading-4 text-[#475467]"><colgroup><col className="w-[130px]" /><col /><col className="w-[145px]" /><col className="w-[290px]" /></colgroup><tbody>
            <tr><th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-medium"><span className="flex items-center gap-3"><TrendingUp className="size-4 shrink-0" />What changed</span></th><td className="border-b border-r border-[#e0e4e9] p-3 align-top">{lesion.change}</td><th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-normal text-[#667085]">Site</th><td className="border-b border-[#e0e4e9] p-3 align-top">{lesion.location}</td></tr>
            <tr><th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-medium"><span className="flex items-center gap-3"><UsersRound className="size-4 shrink-0" />History</span></th><td className="border-b border-r border-[#e0e4e9] p-3 align-top">{workspace.patient.problems.join(" · ") || "No active problems recorded"}</td><th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-normal text-[#667085]">Observed</th><td className="border-b border-[#e0e4e9] p-3 align-top">{formatWorkspaceDate(lesion.firstObserved, workspace, { month: "short", day: "numeric", year: "numeric" })}</td></tr>
            <tr><th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-medium"><span className="flex items-center gap-3"><ClipboardList className="size-4 shrink-0" />Symptoms</span></th><td className="border-b border-r border-[#e0e4e9] p-3 align-top">{lesion.symptoms.join("; ") || "None recorded"}</td><th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-normal text-[#667085]">Exam</th><td className="border-b border-[#e0e4e9] p-3 align-top">{lesion.dimensions} · {lesion.morphology} · {lesion.border}</td></tr>
            <tr><th scope="row" className="border-r border-[#e0e4e9] p-3 align-top font-medium"><span className="flex items-center gap-3"><ShieldCheck className="size-4 shrink-0" />Approvals</span></th><td className="border-r border-[#e0e4e9] p-3 align-top">{workspace.encounter.proposals.length} source-linked proposals</td><th scope="row" className="border-r border-[#e0e4e9] p-3 align-top font-normal text-[#667085]">Included</th><td className="p-3 align-top">{workspace.encounter.proposals.map((proposal) => proposal.title).join(", ")}</td></tr>
          </tbody></table></div></section>

          <details className="group mt-1"><summary className="mx-auto flex min-h-10 w-fit cursor-pointer list-none items-center gap-2 px-3 text-xs font-medium text-[#0f5cc4] [&::-webkit-details-marker]:hidden">View full chart<ArrowRight className="size-3.5 transition-transform group-open:rotate-90" /></summary><div className="grid border-t border-[#e0e4e9] md:grid-cols-2 xl:grid-cols-4">
            <section className="border-b border-[#e0e4e9] p-4 md:border-r xl:border-b-0" aria-labelledby="clinical-chart-title"><ClipboardCheck className="size-4 text-[#167a83]" /><h3 id="clinical-chart-title" className="mt-2 text-xs font-semibold">Clinical chart</h3><ul className="mt-2 space-y-1 text-[11px] leading-5 text-[#667085]">{workspace.patient.allergies.map((item) => <li key={item}>{item} · allergy</li>)}{workspace.patient.medications.map((item) => <li key={item}>{item} · medication</li>)}{workspace.patient.problems.map((item) => <li key={item}>{item} · problem</li>)}</ul></section>
            <section className="border-b border-[#e0e4e9] p-4 xl:border-b-0 xl:border-r" aria-labelledby="communication-title"><MessageSquareText className="size-4 text-[#167a83]" /><h3 id="communication-title" className="mt-2 text-xs font-semibold">Communication</h3><p className="mt-2 text-[11px] leading-5 text-[#667085]">{lastMessage?.body ?? "No patient message recorded."}</p></section>
            <section className="border-b border-[#e0e4e9] p-4 md:border-r xl:border-b-0" aria-labelledby="diagnostic-plan-title"><Beaker className="size-4 text-[#167a83]" /><h3 id="diagnostic-plan-title" className="mt-2 text-xs font-semibold">Diagnostic closure</h3><p className="mt-2 text-[11px] leading-5 text-[#667085]">{workspace.pathology.summary}</p></section>
            <section className="p-4" aria-labelledby="coverage-title"><FileText className="size-4 text-[#167a83]" /><h3 id="coverage-title" className="mt-2 text-xs font-semibold">Coverage &amp; estimate</h3><p className="mt-2 text-[11px] leading-5 text-[#667085]">{workspace.patient.insurance}{workspace.intake ? ` · $${workspace.intake.eligibility.estimatedResponsibility.toFixed(0)} estimated responsibility` : ""}</p></section>
          </div></details>
        </section>
      </main>

      <Sheet open={modifyOpen} onOpenChange={changeModifyOpen}><SheetContent id="modify-biopsy-plan" className="w-full overflow-y-auto bg-white sm:max-w-[480px]"><SheetHeader className="text-left"><SheetTitle>Modify biopsy plan</SheetTitle><SheetDescription>Saving creates a new version of the encounter note in the database.</SheetDescription></SheetHeader><form onSubmit={saveRecommendation} className="mt-6 space-y-5"><div><label htmlFor="biopsy-recommendation" className="text-sm font-medium text-[#172033]">Recommendation</label><Textarea id="biopsy-recommendation" value={draftRecommendation} onChange={(event) => setDraftRecommendation(event.target.value)} className="mt-2 min-h-32 rounded-md border-[#cfd6df] text-sm leading-6" /></div><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => changeModifyOpen(false)}>Cancel</Button><Button type="submit" disabled={!draftRecommendation.trim() || busy !== null} className="bg-[#0f5cc4] text-white hover:bg-[#0b4ea9]">{busy === "modify" ? <LoaderCircle className="size-4 animate-spin" /> : null}Save changes</Button></div></form></SheetContent></Sheet>
    </ScreenFrame>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  AudioLines,
  Beaker,
  BrainCircuit,
  Camera,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  FilePenLine,
  Layers3,
  MapPin,
  MessageSquareText,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Tag,
  UserRound,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { PageHeader, SectionHeader, StatusBadge } from "@/components/product/page-elements";
import { useDemoSession } from "@/components/system/app-providers";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest, endpoints } from "@/lib/api/client";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { formatInTimeZone } from "@/lib/date";
import { cn } from "@/lib/utils";

function BodyMap({ selected, lesionLabel, onSelect }: { selected: boolean; lesionLabel: string; onSelect: () => void }) {
  return (
    <div className="rounded-lg border bg-muted/20 p-4">
      <div className="mb-3 flex items-center justify-between"><p className="text-xs font-semibold">Posterior body map</p><StatusBadge tone="neutral">Back</StatusBadge></div>
      <div className="relative mx-auto h-64 w-40" aria-label="Interactive posterior body map">
        <div className="absolute left-1/2 top-1 h-11 w-10 -translate-x-1/2 rounded-[48%_48%_44%_44%] border bg-card" />
        <div className="absolute left-1/2 top-11 h-28 w-[74px] -translate-x-1/2 rounded-[34%_34%_22%_22%] border bg-card" />
        <div className="absolute left-[18px] top-[54px] h-28 w-7 rotate-[8deg] rounded-full border bg-card" />
        <div className="absolute right-[18px] top-[54px] h-28 w-7 -rotate-[8deg] rounded-full border bg-card" />
        <div className="absolute left-[48px] top-[145px] h-28 w-8 rotate-[2deg] rounded-full border bg-card" />
        <div className="absolute right-[48px] top-[145px] h-28 w-8 -rotate-[2deg] rounded-full border bg-card" />
        <button
          type="button"
          onClick={onSelect}
          aria-pressed={selected}
          aria-label="Select lesion on left posterior shoulder"
          className={cn("absolute left-[42px] top-[63px] z-10 flex size-7 items-center justify-center rounded-full border-2 border-background shadow-sm ring-offset-2 transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", selected ? "bg-rose-600 ring-2 ring-rose-200" : "bg-rose-500")}
        >
          <span className="size-1.5 rounded-full bg-white" />
        </button>
        <div className="absolute left-[3px] top-[57px] h-px w-9 bg-rose-300" />
        <span className="absolute -left-3 top-12 w-14 truncate text-right text-[9px] font-medium text-rose-800">{lesionLabel}</span>
      </div>
      <Button variant="outline" size="sm" className="mt-1 w-full" onClick={onSelect}><MapPin className="size-3.5" /> Left posterior shoulder</Button>
    </div>
  );
}

interface DraftReceipt {
  note: { id: string; updatedAt: string };
  version: { versionNumber: number; createdAt: string };
}

interface ObservationReceipt {
  observationId: string;
  recordedAt: string;
}

interface ObservationForm {
  site: string;
  view: string;
  lengthMm: string;
  widthMm: string;
  morphology: string;
  border: string;
  pigment: string;
  change: string;
  symptoms: string;
  assessment: string;
  comparison: string;
}

export function EncounterWorkspace() {
  const { encounterReview, updateEncounterReview } = useDemoSession();
  const { data, mode, error, refetch } = useDemoBootstrap();
  const queryClient = useQueryClient();
  const [selectedLesion, setSelectedLesion] = useState(true);
  const [selectedProposalOverride, setSelectedProposalOverride] = useState<Set<string> | null>(() => encounterReview.selectedProposalIds.length > 0 ? new Set(encounterReview.selectedProposalIds) : null);
  const [noteDraft, setNoteDraft] = useState(encounterReview.noteDraft);
  const [noteDirty, setNoteDirty] = useState(false);
  const [draftReceipt, setDraftReceipt] = useState<DraftReceipt | null>(null);
  const [observationReceipt, setObservationReceipt] = useState<ObservationReceipt | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState<"note" | "observation" | null>(null);
  const [observationOverride, setObservationOverride] = useState<ObservationForm | null>(null);

  if (mode === "loading") return <PageLoading label="Opening AI encounter workspace" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  if (!data.patient || !data.encounter || !data.pathology) return <WorkspaceUnavailable title="The clinical encounter is not available for your role" />;
  const patient = data.patient;
  const encounter = data.encounter;
  const providerCanMutate = data.session.persona === "provider";
  const noteLocked = encounter.note.status !== "draft";
  const proposalIds = encounter.proposals.map((proposal) => proposal.id);
  const selectedProposals = selectedProposalOverride ?? new Set(proposalIds);

  function toggleProposal(id: string, checked: boolean) {
    if (!providerCanMutate || noteLocked) return;
    setSelectedProposalOverride((current) => {
      const next = new Set(current ?? proposalIds);
      if (checked) next.add(id); else next.delete(id);
      updateEncounterReview({ selectedProposalIds: [...next] });
      return next;
    });
  }

  const lesion = data.patient.lesion;
  const latestObservation = lesion.latestObservation;
  const persistedObservation: ObservationForm = {
    site: latestObservation.site,
    view: latestObservation.view,
    lengthMm: String(latestObservation.lengthMm),
    widthMm: String(latestObservation.widthMm),
    morphology: latestObservation.morphology,
    border: latestObservation.border,
    pigment: latestObservation.pigmentation,
    change: latestObservation.changeOverTime,
    symptoms: latestObservation.symptoms.join("; "),
    assessment: latestObservation.assessment ?? "",
    comparison: latestObservation.comparison ?? "",
  };
  const observation = observationOverride ?? persistedObservation;
  const encounterId = data.encounter.id;
  const noteId = data.encounter.noteId;
  const sourceDraftNote = data.encounter.draftNote;
  const lesionId = lesion.id;
  const currentNoteDraft = noteDraft || data.encounter.draftNote.assessmentPlan;
  const appointment = data.schedule.find((item) => item.patient === patient.name);
  const familyHistory = data.patient.problems.find((problem) => problem.toLowerCase().includes("family history")) ?? "Reviewed";
  const codingProposal = data.encounter.proposals.find((proposal) => proposal.category.toLowerCase().includes("cod"));
  const aftercareProposal = data.encounter.proposals.find((proposal) => proposal.category.toLowerCase().includes("patient"));
  const lesionObservations = lesion.observations ?? [];
  const baselineObservation = lesionObservations[0];
  const currentObservation = lesionObservations.at(-1) ?? latestObservation;
  const lengthChange = baselineObservation ? currentObservation.lengthMm - baselineObservation.lengthMm : null;
  const widthChange = baselineObservation ? currentObservation.widthMm - baselineObservation.widthMm : null;
  const connectedThread = [
    { label: "Intake ready", detail: "History + coverage", complete: true, current: false },
    { label: "Lesion evidence", detail: `${lesionObservations.length || 1} observations + 2 images`, complete: true, current: false },
    { label: "Clinician review", detail: noteLocked ? "Signed record" : `${selectedProposals.size} actions to review`, complete: noteLocked, current: !noteLocked },
    { label: "Durable actions", detail: encounter.completionReceipt ? "8 linked records" : "Awaiting approval", complete: Boolean(encounter.completionReceipt), current: noteLocked && !encounter.completionReceipt },
    { label: "Pathology closure", detail: !noteLocked ? "Created on approval" : data.pathology.status === "notified" ? "Patient notified" : data.pathology.status === "pending" ? "Safety task pending" : "Result in review", complete: data.pathology.status === "notified", current: noteLocked && data.pathology.status !== "notified" },
  ];

  function updateObservation(next: Partial<ObservationForm>) {
    setObservationOverride((current) => ({ ...(current ?? persistedObservation), ...next }));
    setObservationReceipt(null);
  }

  function prepareReview() {
    updateEncounterReview({ selectedProposalIds: [...selectedProposals] });
  }

  async function saveNoteDraft() {
    if (mode !== "live" || !providerCanMutate || noteLocked) return;
    setSaving("note");
    setSaveError(null);
    try {
      const structuredContent = { ...sourceDraftNote, assessmentPlan: currentNoteDraft };
      const content = [structuredContent.chiefConcern, structuredContent.historyOfPresentIllness, structuredContent.focusedExam, structuredContent.assessmentPlan].join("\n\n");
      const receipt = await apiRequest<DraftReceipt>(endpoints.noteDraft(noteId), { method: "PATCH", body: { content, structuredContent, reason: "Clinician updated assessment and plan during encounter review." } });
      setDraftReceipt(receipt);
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
      setNoteDirty(false);
      updateEncounterReview({ noteDraft: "" });
    } catch (draftError) {
      setSaveError(draftError instanceof Error ? draftError.message : "The note draft could not be saved.");
    } finally {
      setSaving(null);
    }
  }

  async function saveObservation() {
    if (mode !== "live" || !providerCanMutate || noteLocked) return;
    setSaving("observation");
    setSaveError(null);
    try {
      const receipt = await apiRequest<ObservationReceipt>(endpoints.lesionObservation, { method: "POST", body: { lesionId, encounterId, site: observation.site, view: observation.view, lengthMm: Number(observation.lengthMm), widthMm: Number(observation.widthMm), morphology: observation.morphology, border: observation.border, pigmentation: observation.pigment, changeOverTime: observation.change, symptoms: observation.symptoms.split(";").map((item) => item.trim()).filter(Boolean), assessment: observation.assessment || null, comparison: observation.comparison || null } });
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
      setObservationOverride(null);
      setObservationReceipt(receipt);
    } catch (observationError) {
      setSaveError(observationError instanceof Error ? observationError.message : "The lesion observation could not be saved.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow={`Encounter${appointment ? ` · ${appointment.time}` : ""}`}
        title="Changing lesion consultation"
        description={`${patient.name} · ${appointment?.provider ?? encounter.note.author.name} · ${data.organization.location} · In person`}
        actions={<><StatusBadge tone={noteLocked ? "success" : providerCanMutate ? "warning" : "neutral"}><Clock3 className="size-3" /> {providerCanMutate ? encounter.note.status : "Read-only coordinator view"}</StatusBadge><Button asChild variant="outline"><Link href="/patients/sarah-mitchell"><UserRound className="size-4" /> Chart</Link></Button>{noteLocked ? <Button asChild><Link href="/pathology">Continue to pathology <ArrowRight className="size-4" /></Link></Button> : !providerCanMutate ? null : noteDirty ? <Button disabled data-testid="review-complete" title="Save note edits before review">Save edits before review <ArrowRight className="size-4" /></Button> : <Button asChild data-testid="review-complete"><Link href="/encounters/sarah-biopsy/review" onClick={prepareReview}>Review & complete <ArrowRight className="size-4" /></Link></Button>}</>}
      />

      {!providerCanMutate ? <Alert className="border-sky-200 bg-sky-50" data-testid="clinical-read-only"><ShieldCheck className="size-4 text-sky-700" /><AlertTitle>Coordinator view</AlertTitle><AlertDescription>You can review the encounter, images, and workflow status. Note edits, clinical approvals, and lesion observations require the assigned provider.</AlertDescription></Alert> : null}

      <Card className="overflow-hidden border-primary/20" data-testid="connected-care-thread">
        <CardContent className="p-0">
          <div className="flex flex-col gap-1 border-b bg-primary/[0.035] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="text-xs font-semibold">One connected care thread</p><p className="text-[11px] text-muted-foreground">Every step stays attached to Sarah, this lesion, and the accountable next action.</p></div>
            <StatusBadge tone="info">Patient → lesion → result → claim</StatusBadge>
          </div>
          <div className="grid md:grid-cols-5">
            {connectedThread.map((step, index) => (
              <div key={step.label} className="relative border-b px-4 py-3 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0">
                <div className="flex items-center gap-2">
                  <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-full border font-mono text-[9px]", step.complete ? "border-emerald-600 bg-emerald-600 text-white" : step.current ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background text-muted-foreground")}>{step.complete ? <Check className="size-3" /> : index + 1}</span>
                  <p className="text-[11px] font-semibold">{step.label}</p>
                </div>
                <p className="mt-1 pl-7 text-[10px] text-muted-foreground">{step.detail}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 2xl:grid-cols-[260px_minmax(0,1fr)_340px]">
        <aside className="space-y-4">
          <Card><CardHeader className="pb-3"><SectionHeader title="Patient context" action={<StatusBadge tone="success">{data.patient.readiness}% ready</StatusBadge>} /></CardHeader><CardContent className="space-y-3 text-xs"><div className="flex justify-between"><span className="text-muted-foreground">Age</span><span>{data.patient.age}</span></div><div className="flex justify-between gap-3"><span className="text-muted-foreground">Allergy</span><span className="text-right">{data.patient.allergies[0] ?? "None recorded"}</span></div><div className="flex justify-between gap-3"><span className="text-muted-foreground">Family history</span><span className="text-right">{familyHistory}</span></div><div className="flex justify-between gap-3"><span className="text-muted-foreground">Coverage</span><span className="text-right">{data.patient.insurance}</span></div><Separator /><p className="leading-5 text-muted-foreground">{data.encounter.previsitSummary}</p></CardContent></Card>
          <BodyMap selected={selectedLesion} lesionLabel={lesion.id} onSelect={() => setSelectedLesion((current) => !current)} />
          <Card><CardHeader className="pb-2"><SectionHeader title="Lesion timeline" action={<Layers3 className="size-4 text-primary" />} /></CardHeader><CardContent className="space-y-0">{encounter.timeline.map((event, index) => <div key={`${event.date}-${event.title}-${index}`} className="relative flex gap-3 pb-4 last:pb-0"><div className="relative flex w-3 justify-center"><span className="z-10 mt-1.5 size-2 rounded-full bg-primary" />{index < encounter.timeline.length - 1 || observationReceipt ? <span className="absolute bottom-0 top-3 w-px bg-border" /> : null}</div><div><p className="font-mono text-[9px] text-muted-foreground">{formatInTimeZone(event.date, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" })}</p><p className="text-[11px] font-semibold">{event.title}</p><p className="mt-0.5 text-[10px] leading-4 text-muted-foreground">{event.detail}</p></div></div>)}{observationReceipt ? <div className="flex gap-3"><div className="flex w-3 justify-center"><span className="mt-1.5 size-2 rounded-full bg-emerald-600" /></div><div><p className="font-mono text-[9px] text-emerald-700">Saved</p><p className="text-[11px] font-semibold">Structured observation</p><p className="mt-0.5 text-[10px] text-muted-foreground">{observationReceipt.observationId}</p></div></div> : null}</CardContent></Card>
        </aside>

        <section className="min-w-0 space-y-4">
          <Card className="border-violet-200/80 bg-violet-50/30">
            <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-violet-100 text-violet-700"><AudioLines className="size-4" /></span>
              <div className="flex-1"><div className="flex items-center gap-2"><p className="text-xs font-semibold">Source transcript available</p><StatusBadge tone="ai">{data.encounter.transcript.length} segments</StatusBadge></div><p className="mt-0.5 text-[11px] text-muted-foreground">Consent {data.encounter.note.consent.status} · {data.encounter.note.consent.version} · accepted {formatInTimeZone(data.encounter.note.consent.acceptedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}. AI run {data.encounter.aiProvenance.aiRunId} used {data.encounter.aiProvenance.model} ({data.encounter.aiProvenance.promptVersion}).</p></div>
            </CardContent>
          </Card>

          <Tabs defaultValue="note">
            <TabsList className="mb-4"><TabsTrigger value="note"><FilePenLine className="size-3.5" /> Structured note</TabsTrigger><TabsTrigger value="transcript"><AudioLines className="size-3.5" /> Transcript</TabsTrigger><TabsTrigger value="images"><Camera className="size-3.5" /> Images</TabsTrigger><TabsTrigger value="lesion"><ScanSearch className="size-3.5" /> Lesion</TabsTrigger></TabsList>

            <TabsContent value="note" className="mt-0 space-y-4">
              <Card>
                <CardHeader className="border-b pb-3"><SectionHeader title="Encounter note" description={`Version ${data.encounter.note.currentVersion.number} · ${data.encounter.note.author.name} · ${data.encounter.note.status}`} action={<span data-testid="note-version" data-version={data.encounter.note.currentVersion.number}><StatusBadge tone={noteLocked ? "success" : "ai"}><Sparkles className="size-3" /> {noteLocked ? "Signed record" : "AI-assisted draft"}</StatusBadge></span>} /></CardHeader>
                <CardContent className="space-y-5 p-5">
                  <section><div className="flex items-center justify-between"><h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Chief concern</h3><StatusBadge tone="neutral">Source draft</StatusBadge></div><p className="mt-2 text-sm leading-6">{data.encounter.draftNote.chiefConcern}</p></section>
                  <Separator />
                  <section><div className="flex items-center justify-between"><h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">History of present illness</h3><StatusBadge tone="ai">Proposed</StatusBadge></div><p className="mt-2 text-sm leading-6">{data.encounter.draftNote.historyOfPresentIllness}</p></section>
                  <Separator />
                  <section><div className="flex items-center justify-between"><h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Focused examination</h3><StatusBadge tone="ai">Proposed</StatusBadge></div><p className="mt-2 text-sm leading-6">{data.encounter.draftNote.focusedExam}</p></section>
                  <Separator />
                  <section><div className="flex items-center justify-between"><h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Assessment & plan</h3><StatusBadge tone={noteLocked ? "success" : !providerCanMutate ? "neutral" : noteDirty ? "warning" : draftReceipt ? "success" : "ai"}>{noteLocked ? encounter.note.status : !providerCanMutate ? "Provider edit required" : noteDirty ? "Unsaved edits" : draftReceipt ? `Draft v${draftReceipt.version.versionNumber}` : "AI proposal"}</StatusBadge></div><Textarea aria-label="Assessment and plan" className="mt-2 min-h-28 bg-background text-sm leading-6" value={currentNoteDraft} readOnly={noteLocked || !providerCanMutate} onChange={(event) => { if (noteLocked || !providerCanMutate) return; setNoteDraft(event.target.value); setNoteDirty(true); updateEncounterReview({ noteDraft: event.target.value }); }} /><div className="mt-2 flex items-center justify-between gap-3"><p className="text-[10px] text-muted-foreground">{noteLocked ? "Signed content is read-only; later corrections require a linked amendment." : !providerCanMutate ? "The assigned provider must edit and sign this draft." : "Saving creates a versioned server draft; signing occurs only at completion."}</p>{!noteLocked && providerCanMutate ? <Button type="button" variant="outline" size="sm" onClick={() => void saveNoteDraft()} disabled={mode !== "live" || saving !== null || !noteDirty} data-testid="save-note-draft">{saving === "note" ? "Saving…" : "Save draft"}</Button> : null}</div>{draftReceipt ? <p className="mt-2 font-mono text-[10px] text-emerald-700" data-testid="note-draft-receipt">{draftReceipt.note.id} · saved {formatInTimeZone(draftReceipt.version.createdAt, data.organization.timezone, { hour: "numeric", minute: "2-digit" })}</p> : null}{saveError ? <p className="mt-2 text-xs text-destructive">{saveError}</p> : null}</section>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="transcript" className="mt-0">
              <Card><CardHeader className="border-b pb-3"><SectionHeader title="Ambient transcript" description="Speaker-attributed source; timestamps are linked to drafted note sections." action={<StatusBadge tone="info">API source</StatusBadge>} /></CardHeader><CardContent className="p-0"><ScrollArea className="h-[520px]"><div className="divide-y">{data.encounter.transcript.map((line) => <div key={`${line.time}-${line.speaker}`} className="grid grid-cols-[48px_84px_1fr] gap-3 p-4 text-xs"><span className="font-mono text-[10px] text-muted-foreground">{line.time}</span><span className="font-semibold">{line.speaker}</span><p className="leading-5 text-foreground/85">{line.text}</p></div>)}</div></ScrollArea></CardContent></Card>
            </TabsContent>

            <TabsContent value="images" className="mt-0">
              <Card>
                <CardHeader className="border-b pb-3"><SectionHeader title="Longitudinal lesion review" description={`Clinical overview, dermoscopy, and ${lesionObservations.length || 1} durable observations remain attached to one lesion record.`} action={<StatusBadge tone="success">Site-linked</StatusBadge>} /></CardHeader>
                <CardContent className="space-y-5 p-5">
                  <div className="grid gap-4 lg:grid-cols-2">
                    <figure>
                      <div className="relative aspect-[3/2] overflow-hidden rounded-lg border bg-muted"><Image src={lesion.overviewImage.url} alt="Synthetic overview clinical photograph of Sarah Mitchell’s left posterior shoulder lesion" fill className="object-cover" sizes="(max-width: 1024px) 100vw, 520px" priority /></div>
                      <figcaption className="mt-2 flex items-start justify-between gap-3 text-xs"><span><span className="font-semibold">Clinical overview</span><span className="block text-[10px] text-muted-foreground">{formatInTimeZone(lesion.overviewImage.capturedAt, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" })} · {lesion.overviewImage.id}</span></span><StatusBadge tone="success">File verified</StatusBadge></figcaption>
                    </figure>
                    <figure>
                      <div className="relative aspect-[3/2] overflow-hidden rounded-lg border bg-black"><Image src={lesion.dermoscopyImage.url} alt="Synthetic dermoscopic view of Sarah Mitchell’s pigmented left posterior shoulder lesion" fill className="object-contain" sizes="(max-width: 1024px) 100vw, 520px" /></div>
                      <figcaption className="mt-2 flex items-start justify-between gap-3 text-xs"><span><span className="font-semibold">Dermoscopy · same lesion</span><span className="block text-[10px] text-muted-foreground">{formatInTimeZone(lesion.dermoscopyImage.capturedAt, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" })} · {lesion.dermoscopyImage.id}</span></span><StatusBadge tone="ai">Features proposed</StatusBadge></figcaption>
                    </figure>
                  </div>

                  <div className="grid gap-3 lg:grid-cols-[1.05fr_1fr]">
                    <div className="rounded-lg border bg-muted/25 p-4">
                      <div className="flex items-center justify-between gap-3"><p className="text-xs font-semibold">Measured change over time</p><StatusBadge tone="warning">Clinician review</StatusBadge></div>
                      {baselineObservation ? <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                        <div><p className="font-mono text-xl font-semibold">{baselineObservation.lengthMm} × {baselineObservation.widthMm} mm</p><p className="mt-1 text-[10px] text-muted-foreground">Patient baseline · {formatInTimeZone(baselineObservation.observedAt, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" })}</p></div>
                        <ArrowRight className="size-4 text-muted-foreground" />
                        <div className="text-right"><p className="font-mono text-xl font-semibold">{currentObservation.lengthMm} × {currentObservation.widthMm} mm</p><p className="mt-1 text-[10px] text-muted-foreground">Clinician exam · {formatInTimeZone(currentObservation.observedAt, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" })}</p></div>
                      </div> : <p className="mt-3 text-xs text-muted-foreground">No comparable baseline measurement is available.</p>}
                      <div className="mt-4 flex flex-wrap gap-2"><StatusBadge tone="warning">Length {lengthChange == null ? "—" : `${lengthChange >= 0 ? "+" : ""}${lengthChange.toFixed(1)} mm`}</StatusBadge><StatusBadge tone="warning">Width {widthChange == null ? "—" : `${widthChange >= 0 ? "+" : ""}${widthChange.toFixed(1)} mm`}</StatusBadge></div>
                      <p className="mt-3 text-xs leading-5 text-muted-foreground">{currentObservation.changeOverTime}</p>
                    </div>
                    <div className="rounded-lg border p-4">
                      <p className="text-xs font-semibold">Structured dermoscopy context</p>
                      <dl className="mt-3 grid gap-x-4 gap-y-3 text-xs sm:grid-cols-2">
                        <div><dt className="text-[10px] text-muted-foreground">Morphology</dt><dd className="mt-0.5 font-medium">{currentObservation.morphology}</dd></div>
                        <div><dt className="text-[10px] text-muted-foreground">Border</dt><dd className="mt-0.5 font-medium">{currentObservation.border}</dd></div>
                        <div><dt className="text-[10px] text-muted-foreground">Pigment</dt><dd className="mt-0.5 font-medium">{currentObservation.pigmentation}</dd></div>
                        <div><dt className="text-[10px] text-muted-foreground">Symptoms</dt><dd className="mt-0.5 font-medium">{currentObservation.symptoms.join(", ") || "None recorded"}</dd></div>
                      </dl>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 border-t pt-4 text-[10px] text-muted-foreground"><Camera className="size-3.5 text-primary" /><span className="font-medium text-foreground">Clinical overview</span><ArrowRight className="size-3" /><span className="font-mono">{lesion.id}</span><ArrowRight className="size-3" /><span className="font-mono">{encounter.id}</span><ArrowRight className="size-3" /><span>{noteLocked ? "Specimen + pathology order linked" : "Specimen + order created on approval"}</span></div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="lesion" className="mt-0">
              <Card><CardHeader className="border-b pb-3"><SectionHeader title={`${lesion.id} · ${observation.site}`} description={`Latest durable observation · ${latestObservation.source} · ${formatInTimeZone(latestObservation.observedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`} action={observationReceipt ? <StatusBadge tone="success">Saved to timeline</StatusBadge> : observationOverride ? <StatusBadge tone="warning">Unsaved changes</StatusBadge> : <StatusBadge tone="neutral">Saved observation</StatusBadge>} /></CardHeader><CardContent className="space-y-5 p-5"><div className="grid gap-4 sm:grid-cols-2"><div><Label htmlFor="lesion-site">Anatomical site</Label><Input id="lesion-site" className="mt-1.5" value={observation.site} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ site: event.target.value })} /></div><div><Label htmlFor="lesion-view">Body-map view</Label><select id="lesion-view" className="mt-1.5 flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm" value={observation.view} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ view: event.target.value })}><option value="posterior">Posterior</option><option value="anterior">Anterior</option><option value="left-lateral">Left lateral</option><option value="right-lateral">Right lateral</option></select></div><div><Label htmlFor="lesion-length">Length (mm)</Label><Input id="lesion-length" type="number" min="0" step="0.1" className="mt-1.5" value={observation.lengthMm} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ lengthMm: event.target.value })} /></div><div><Label htmlFor="lesion-width">Width (mm)</Label><Input id="lesion-width" type="number" min="0" step="0.1" className="mt-1.5" value={observation.widthMm} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ widthMm: event.target.value })} /></div><div><Label htmlFor="lesion-morphology">Morphology</Label><Input id="lesion-morphology" className="mt-1.5" value={observation.morphology} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ morphology: event.target.value })} /></div><div><Label htmlFor="lesion-border">Border</Label><Input id="lesion-border" className="mt-1.5" value={observation.border} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ border: event.target.value })} /></div></div><div><Label htmlFor="lesion-pigment">Pigmentation</Label><Input id="lesion-pigment" className="mt-1.5" value={observation.pigment} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ pigment: event.target.value })} /></div><div><Label htmlFor="lesion-change">Change over time</Label><Textarea id="lesion-change" className="mt-1.5 min-h-20" value={observation.change} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ change: event.target.value })} /></div><div className="grid gap-4 sm:grid-cols-2"><div><Label htmlFor="lesion-symptoms">Symptoms (semicolon separated)</Label><Textarea id="lesion-symptoms" className="mt-1.5 min-h-20" value={observation.symptoms} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ symptoms: event.target.value })} /></div><div><Label htmlFor="lesion-assessment">Assessment</Label><Textarea id="lesion-assessment" className="mt-1.5 min-h-20" value={observation.assessment} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ assessment: event.target.value })} /></div></div><div><Label htmlFor="lesion-comparison">Prior comparison</Label><Textarea id="lesion-comparison" className="mt-1.5 min-h-20" value={observation.comparison} disabled={!providerCanMutate || noteLocked} onChange={(event) => updateObservation({ comparison: event.target.value })} /></div>{observationReceipt ? <Alert className="border-emerald-200 bg-emerald-50" data-testid="lesion-observation-receipt"><CheckCircle2 className="size-4 text-emerald-700" /><AlertTitle>Timeline event saved</AlertTitle><AlertDescription>Observation {observationReceipt.observationId} recorded {formatInTimeZone(observationReceipt.recordedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}.</AlertDescription></Alert> : null}{saveError ? <Alert variant="destructive"><AlertTitle>Nothing was saved</AlertTitle><AlertDescription>{saveError}</AlertDescription></Alert> : null}<div className="flex justify-end"><Button type="button" onClick={() => void saveObservation()} disabled={mode !== "live" || !providerCanMutate || noteLocked || saving !== null || !observationOverride} data-testid="save-lesion-observation">{!providerCanMutate ? "Provider entry required" : saving === "observation" ? "Saving…" : observationOverride ? "Save observation" : "No changes to save"} <Check className="size-4" /></Button></div></CardContent></Card>
            </TabsContent>
          </Tabs>
        </section>

        <aside className="space-y-4">
          <Card className="sticky top-20 border-violet-200/80">
            <CardHeader className="border-b bg-violet-50/45 pb-3"><SectionHeader title={noteLocked ? "One review · actions recorded" : `One review → ${selectedProposals.size} linked actions`} description={noteLocked ? "Every approved handoff is durable and no longer editable here." : "Nothing changes the chart until clinician approval."} action={<StatusBadge tone={noteLocked ? "success" : "ai"}><BrainCircuit className="size-3" /> {selectedProposals.size}</StatusBadge>} /></CardHeader>
            <CardContent className="space-y-2 p-3">
              {data.encounter.proposals.map((proposal) => (
                <label key={proposal.id} className={cn("flex gap-3 rounded-lg border p-3", !noteLocked && providerCanMutate && "cursor-pointer", selectedProposals.has(proposal.id) && "border-violet-200 bg-violet-50/50")}>
                  <Checkbox checked={selectedProposals.has(proposal.id)} disabled={noteLocked || !providerCanMutate} onCheckedChange={(checked) => toggleProposal(proposal.id, checked === true)} />
                  <span className="min-w-0 flex-1"><span className="flex items-center gap-2"><span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-violet-700">{proposal.category}</span>{proposal.required ? <span className="text-[9px] text-muted-foreground">Required</span> : null}</span><span className="mt-1 block text-xs font-semibold">{proposal.title}</span><span className="mt-1 block text-[10px] leading-4 text-muted-foreground">{proposal.detail}</span></span>
                </label>
              ))}
              {noteLocked ? <Button asChild className="mt-2 w-full"><Link href="/pathology"><ClipboardCheck className="size-4" /> Encounter signed · open pathology <ChevronRight className="size-3.5" /></Link></Button> : !providerCanMutate ? <Button className="mt-2 w-full" disabled data-testid="review-actions"><ClipboardCheck className="size-4" /> Provider approval required <ChevronRight className="size-3.5" /></Button> : noteDirty ? <Button className="mt-2 w-full" disabled data-testid="review-actions" title="Save note edits before review"><ClipboardCheck className="size-4" /> Save edits before review <ChevronRight className="size-3.5" /></Button> : <Button asChild className="mt-2 w-full" data-testid="review-actions"><Link href="/encounters/sarah-biopsy/review" onClick={prepareReview}><ClipboardCheck className="size-4" /> Review {selectedProposals.size} actions <ChevronRight className="size-3.5" /></Link></Button>}
              <p className="text-center text-[10px] leading-4 text-muted-foreground">Final approval records author, timestamp, note version, provenance, and audit events.</p>
            </CardContent>
          </Card>

          <Card><CardHeader className="pb-2"><SectionHeader title="Coding support" action={<Tag className="size-4 text-primary" />} /></CardHeader><CardContent className="space-y-2"><div className="rounded-md border p-3"><div className="flex items-center justify-between"><span className="text-xs font-semibold">{codingProposal?.title ?? "Coding proposal"}</span><StatusBadge tone="ai">Suggested</StatusBadge></div><p className="mt-2 text-[10px] leading-4 text-muted-foreground">{codingProposal?.detail}</p></div><Alert className="mt-3 border-emerald-200 bg-emerald-50"><CheckCircle2 className="size-4 text-emerald-700" /><AlertTitle>Documentation supports selection</AlertTitle><AlertDescription>Site, method, medical necessity, and specimen are present.</AlertDescription></Alert></CardContent></Card>

          <Card><CardContent className="space-y-3 p-4"><div className="flex items-center gap-3"><span className="flex size-8 items-center justify-center rounded-md bg-primary/8 text-primary"><Beaker className="size-4" /></span><div><p className="text-xs font-semibold">Pathology handoff</p><p className="text-[10px] text-muted-foreground">Closure due {formatInTimeZone(data.pathology.closureDueAt, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" })}</p></div></div><div className="flex items-center gap-3"><span className="flex size-8 items-center justify-center rounded-md bg-primary/8 text-primary"><MessageSquareText className="size-4" /></span><div><p className="text-xs font-semibold">Patient aftercare</p><p className="text-[10px] text-muted-foreground">{aftercareProposal?.title ?? "Review patient communication"}</p></div></div><div className="flex items-center gap-3"><span className="flex size-8 items-center justify-center rounded-md bg-primary/8 text-primary"><Stethoscope className="size-4" /></span><div><p className="text-xs font-semibold">Claim draft</p><p className="text-[10px] text-muted-foreground">Created only after approval</p></div></div></CardContent></Card>
        </aside>
      </div>
    </div>
  );
}

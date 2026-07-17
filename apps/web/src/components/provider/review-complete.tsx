"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, ArrowRight, Beaker, Check, CheckCircle2, ClipboardCheck, FileLock2, MessageSquareText, ReceiptText, ShieldCheck, Sparkles, UserRoundCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader, SectionHeader, StatusBadge } from "@/components/product/page-elements";
import { useDemoSession } from "@/components/system/app-providers";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { apiRequest, endpoints } from "@/lib/api/client";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { formatInTimeZone } from "@/lib/date";
import { cn } from "@/lib/utils";

const actionIcons = [FileLock2, UserRoundCheck, Beaker, ReceiptText, MessageSquareText, ShieldCheck];

interface EncounterCompletionReceipt {
  encounterId: string;
  status: string;
  signedAt: string;
  noteId: string;
  noteVersion: number;
  consentId: string;
  procedureId: string;
  specimenId: string;
  orderId: string;
  claimId: string;
  messageId: string;
  closureTaskId: string;
}

export function ReviewComplete() {
  const { encounterReview } = useDemoSession();
  const { data, mode, error, refetch } = useDemoBootstrap();
  const queryClient = useQueryClient();
  const [selectedOverride, setSelectedOverride] = useState<Set<string> | null>(() => encounterReview.selectedProposalIds.length > 0 ? new Set(encounterReview.selectedProposalIds) : null);
  const [confirm, setConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [receipt, setReceipt] = useState<EncounterCompletionReceipt | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  if (mode === "loading") return <PageLoading label="Preparing encounter review" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  if (!data.encounter) return <WorkspaceUnavailable title="Encounter approval is not available for your role" />;
  if (data.session.persona !== "provider") return <WorkspaceUnavailable title="Assigned provider approval required" description="Clinical coordinators can review the encounter workspace, but only the assigned provider can sign the note and approve downstream actions." />;
  const persistedReceipt = data.encounter.completionReceipt;
  const completionReceipt: EncounterCompletionReceipt | null = receipt ?? (persistedReceipt ? {
    ...persistedReceipt,
    encounterId: data.encounter.id,
    noteVersion: data.encounter.note.currentVersion.number,
  } : null);
  const proposalIds = data.encounter.proposals.map((proposal) => proposal.id);
  const selected = selectedOverride ?? new Set(proposalIds);
  const encounterId = data.encounter.id;
  const expectedNoteVersion = data.encounter.note.currentVersion.number;
  const expectedNoteHash = data.encounter.note.currentVersion.contentHash;

  const requiredSelected = data.encounter.proposals.filter((proposal) => proposal.required).every((proposal) => selected.has(proposal.id));

  function toggle(id: string, checked: boolean) {
    setSelectedOverride((current) => { const next = new Set(current ?? proposalIds); if (checked) next.add(id); else next.delete(id); return next; });
  }

  async function completeEncounter() {
    if (mode !== "live" || !requiredSelected || !confirm) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const nextReceipt = await apiRequest<EncounterCompletionReceipt>(endpoints.encounterComplete(encounterId), { method: "POST", body: { proposedActionIds: [...selected], expectedNoteVersion, expectedNoteHash, attest: true, signNote: true, attestation: "I reviewed the source record and approve the selected actions." } });
      setReceipt(nextReceipt);
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
    } catch (completionError) {
      setSubmitError(completionError instanceof Error ? completionError.message : "The encounter could not be completed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (completionReceipt) {
    return (
      <div className="mx-auto max-w-3xl space-y-6 py-8">
        <div className="text-center"><span className="mx-auto flex size-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><Check className="size-7" /></span><StatusBadge tone="success" className="mt-4">Encounter complete</StatusBadge><h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em]">Every approved handoff is in motion.</h1><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted-foreground">The note is signed and immutable, the specimen and order are linked, aftercare is queued, the claim is drafted, and pathology closure is being tracked.</p></div>
        <Card data-testid="encounter-completion-receipt"><CardContent className="grid gap-3 p-5 sm:grid-cols-2">{[
          { icon: FileLock2, title: "Note signed", detail: `${completionReceipt.noteId} · v${completionReceipt.noteVersion} · ${formatInTimeZone(completionReceipt.signedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}` },
          { icon: ShieldCheck, title: "Consent linked", detail: completionReceipt.consentId },
          { icon: UserRoundCheck, title: "Procedure recorded", detail: completionReceipt.procedureId },
          { icon: Beaker, title: "Pathology order created", detail: completionReceipt.orderId },
          { icon: Beaker, title: "Specimen ordered", detail: completionReceipt.specimenId },
          { icon: MessageSquareText, title: "Aftercare sent", detail: completionReceipt.messageId },
          { icon: ReceiptText, title: "Claim drafted", detail: completionReceipt.claimId },
          { icon: ClipboardCheck, title: "Closure task created", detail: completionReceipt.closureTaskId },
        ].map((item) => { const Icon = item.icon; return <div key={item.title} className="flex gap-3 rounded-lg border p-4"><Icon className="size-4 shrink-0 text-emerald-700" /><div className="min-w-0"><p className="text-xs font-semibold">{item.title}</p><p className="break-all font-mono text-[10px] text-muted-foreground">{item.detail}</p></div></div>; })}</CardContent></Card>
        <div className="flex flex-wrap justify-center gap-2"><Button asChild><Link href="/pathology">Continue to pathology <ArrowRight className="size-4" /></Link></Button><Button asChild variant="outline"><Link href="/messages">View patient message</Link></Button><Button asChild variant="ghost"><Link href="/patients/sarah-mitchell">Return to chart</Link></Button></div>
      </div>
    );
  }

  if (data.encounter.note.status !== "draft") {
    return <WorkspaceUnavailable title="This encounter is already complete" description="The signed note is read-only. Refresh to load its durable completion receipt." />;
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Human approval checkpoint" title="Review and complete" description="Approve the clinical, operational, financial, and patient-facing changes that will be committed as one auditable workflow." actions={<Button asChild variant="outline"><Link href="/encounters/sarah-biopsy"><ArrowLeft className="size-4" /> Back to note</Link></Button>} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader className="border-b pb-4"><SectionHeader title="Actions requiring approval" description={`${selected.size} of ${data.encounter.proposals.length} selected · required actions must remain selected`} action={<StatusBadge tone="ai"><Sparkles className="size-3" /> AI proposed</StatusBadge>} /></CardHeader>
          <CardContent className="divide-y p-0">
            {data.encounter.proposals.map((proposal, index) => {
              const Icon = actionIcons[index] ?? ClipboardCheck;
              return (
                <label key={proposal.id} className={cn("flex cursor-pointer gap-4 p-5 hover:bg-muted/25", selected.has(proposal.id) && "bg-violet-50/25")}>
                  <Checkbox checked={selected.has(proposal.id)} onCheckedChange={(checked) => toggle(proposal.id, checked === true)} />
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"><Icon className="size-4" /></span>
                  <span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2"><span className="text-sm font-semibold">{proposal.title}</span>{proposal.required ? <StatusBadge tone="warning">Required</StatusBadge> : <StatusBadge>Optional</StatusBadge>}</span><span className="mt-1 block text-xs leading-5 text-muted-foreground">{proposal.detail}</span><span className="mt-2 block text-[10px] font-semibold uppercase tracking-[0.11em] text-violet-700">{proposal.category} · Proposed action</span></span>
                </label>
              );
            })}
          </CardContent>
        </Card>

        <aside className="space-y-4">
          <Card><CardHeader className="pb-3"><SectionHeader title="Signed-note integrity" action={<FileLock2 className="size-4 text-primary" />} /></CardHeader><CardContent className="space-y-3 text-xs"><p className="leading-5 text-muted-foreground">Completion signs the current server draft at a server timestamp. Later corrections require a linked amendment; signed content is never overwritten.</p><Separator /><div className="flex justify-between"><span className="text-muted-foreground">Author</span><span className="font-medium">{data.encounter.note.author.name}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Current version</span><span className="font-mono">v{data.encounter.note.currentVersion.number} · {data.encounter.note.currentVersion.contentHash}</span></div><div className="flex justify-between"><span className="text-muted-foreground">AI run</span><span className="font-mono">{data.encounter.aiProvenance.aiRunId}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Consent</span><StatusBadge tone={data.encounter.note.consent.status === "active" ? "success" : "danger"}>{data.encounter.note.consent.status}</StatusBadge></div></CardContent></Card>
          <Card className="border-primary/25"><CardHeader className="pb-3"><SectionHeader title="Clinician attestation" /></CardHeader><CardContent className="space-y-4"><label className={cn("flex cursor-pointer gap-3 rounded-lg border p-3", confirm && "border-primary bg-primary/5")}><Checkbox checked={confirm} onCheckedChange={(checked) => setConfirm(checked === true)} /><span className="text-xs leading-5">I reviewed the source transcript, note, orders, codes, patient communication, and safety tasks. I approve the selected actions.</span></label>{!requiredSelected ? <Alert className="border-amber-200 bg-amber-50"><AlertTriangle className="size-4 text-amber-700" /><AlertDescription>Restore every required action before completing.</AlertDescription></Alert> : null}{mode !== "live" ? <Alert className="border-amber-200 bg-amber-50"><AlertTriangle className="size-4 text-amber-700" /><AlertTitle>Read-only preview</AlertTitle><AlertDescription>Completion is disabled until the domain API and durable database are available.</AlertDescription></Alert> : null}{submitError ? <Alert variant="destructive"><AlertTitle>Nothing was committed</AlertTitle><AlertDescription>{submitError}</AlertDescription></Alert> : null}<Button className="w-full" size="lg" onClick={() => void completeEncounter()} disabled={!requiredSelected || !confirm || submitting || mode !== "live"} data-testid="complete-encounter">{submitting ? "Completing…" : "Approve & complete"} <CheckCircle2 className="size-4" /></Button><p className="text-center text-[10px] leading-4 text-muted-foreground">The API applies approved actions transactionally and returns durable record identifiers.</p></CardContent></Card>
        </aside>
      </div>
    </div>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Beaker,
  CalendarCheck2,
  Check,
  CheckCircle2,
  Clock3,
  FileCheck2,
  FlaskConical,
  ImageIcon,
  Link2,
  MessageSquareText,
  Microscope,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { EmptyState, PageHeader, SectionHeader, StatusBadge } from "@/components/product/page-elements";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { apiRequest, endpoints } from "@/lib/api/client";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { formatInTimeZone } from "@/lib/date";

interface PathologyReviewReceipt {
  resultId: string;
  status: string;
  reviewedAt: string;
  notificationId?: string;
  closureTaskId?: string;
  followupId?: string;
}

export function PathologyWorkspace() {
  const { data, mode, error, refetch } = useDemoBootstrap();
  const queryClient = useQueryClient();
  const [receipt, setReceipt] = useState<PathologyReviewReceipt | null>(null);
  const [notifyApproved, setNotifyApproved] = useState(false);
  const [followupApproved, setFollowupApproved] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  if (mode === "loading") return <PageLoading label="Loading pathology work queue" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  if (!data.patient || !data.pathology) return <WorkspaceUnavailable title="Pathology records are not available for your role" />;
  const pathology = data.pathology;
  if (!pathology.id || pathology.status === "pending") {
    return (
      <div className="space-y-5">
        <PageHeader eyebrow="Clinical safety" title="Pathology" description="The encounter is tracked, but no durable pathology result exists yet." actions={<span data-testid="pathology-status" data-status="pending"><StatusBadge tone="warning"><Clock3 className="size-3" /> Awaiting result</StatusBadge></span>} />
        <EmptyState icon={<Beaker className="size-6" />} title="Result pending" description="Use the protected presenter trigger when the lab result is ready. Review and patient notification remain disabled until the API returns a durable result ID." />
      </div>
    );
  }
  const resultId = pathology.id;
  const providerCanMutate = data.session.persona === "provider";
  const isReviewed = pathology.status === "reviewed" || pathology.status === "notified";
  const isNotified = pathology.status === "notified";
  const followupRecorded = Boolean(pathology.followup || receipt?.followupId);
  const hasFollowupAction = followupApproved && !followupRecorded;
  const hasNotificationAction = notifyApproved && !isNotified && Boolean(pathology.patientMessageDraft);

  async function reviewResult() {
    if (mode !== "live" || !providerCanMutate) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const nextReceipt = await apiRequest<PathologyReviewReceipt>(endpoints.pathologyReview(resultId), { method: "POST", body: { notifyPatient: hasNotificationAction, patientMessage: hasNotificationAction ? pathology.patientMessageDraft?.body ?? null : null, createFollowup: hasFollowupAction, disposition: "clinical_monitoring" } });
      setReceipt(nextReceipt);
      setNotifyApproved(false);
      setFollowupApproved(false);
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
    } catch (reviewError) {
      setSubmitError(reviewError instanceof Error ? reviewError.message : "The result could not be reviewed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader eyebrow="Clinical safety" title="Pathology" description="Every specimen remains linked, reviewed, communicated, and closed—with escalation before a patient can be lost to follow-up." actions={<><span data-testid="pathology-status" data-status={pathology.status}><StatusBadge tone={isNotified ? "success" : isReviewed ? "info" : "warning"}>{isNotified ? "Patient notified" : isReviewed ? "Reviewed · notification pending" : "Needs review"}</StatusBadge></span><StatusBadge tone="neutral"><Clock3 className="size-3" /> Closes {formatInTimeZone(pathology.closureDueAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</StatusBadge></>} />

      {pathology.reviewedAt ? <p className="text-[11px] text-muted-foreground">First reviewed <time dateTime={pathology.reviewedAt} data-testid="pathology-reviewed-at">{formatInTimeZone(pathology.reviewedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</time>{pathology.notifiedAt ? <> · Patient notified <time dateTime={pathology.notifiedAt}>{formatInTimeZone(pathology.notifiedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</time></> : null}</p> : null}

      {!providerCanMutate ? <Alert className="border-sky-200 bg-sky-50" data-testid="pathology-read-only"><ShieldCheck className="size-4 text-sky-700" /><AlertTitle>Coordinator view</AlertTitle><AlertDescription>You can monitor result linkage and closure status. Clinical review, patient notification, and follow-up approval require the assigned provider.</AlertDescription></Alert> : null}

      <div className="grid gap-5 2xl:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader className="border-b pb-3"><SectionHeader title="Result to review" description="API-provided result requiring closure" /></CardHeader>
          <CardContent className="divide-y p-0">
            <div className="flex w-full items-start gap-3 bg-primary/5 p-4 text-left">
              <span className={`mt-0.5 flex size-8 items-center justify-center rounded-md ${data.pathology.priority === "high" ? "bg-rose-50 text-rose-700" : "bg-muted text-muted-foreground"}`}><Microscope className="size-4" /></span>
              <span className="min-w-0 flex-1"><span className="flex items-center justify-between"><span className="text-xs font-semibold">{data.patient.name}</span><span className="font-mono text-[9px] text-muted-foreground">{formatInTimeZone(data.pathology.receivedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span></span><span className="mt-1 block text-[11px] text-muted-foreground">{data.patient.lesion.location}</span><span className="mt-2 flex items-center gap-2"><span className="font-mono text-[9px]">{data.pathology.accession}</span><StatusBadge tone={data.pathology.priority === "high" ? "danger" : "neutral"} className="h-4 text-[9px]">{data.pathology.priority}</StatusBadge></span></span>
            </div>
          </CardContent>
        </Card>

        <div className="min-w-0 space-y-5">
          {receipt ? <Alert className={receipt.status === "notified" ? "border-emerald-200 bg-emerald-50" : "border-sky-200 bg-sky-50"} data-testid="pathology-review-receipt"><CheckCircle2 className={receipt.status === "notified" ? "size-4 text-emerald-700" : "size-4 text-sky-700"} /><AlertTitle>Review recorded · {receipt.status}</AlertTitle><AlertDescription>Result {receipt.resultId} reviewed {formatInTimeZone(receipt.reviewedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}. Notification {receipt.notificationId ?? "not requested"}; closure task {receipt.closureTaskId ?? "not returned"}; follow-up {receipt.followupId ?? "not requested"}.</AlertDescription></Alert> : null}
          <Card className="overflow-hidden">
            <div className="flex flex-col gap-4 border-b bg-muted/25 p-5 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold tracking-[-0.03em]">{data.patient.name}</h2><StatusBadge tone={isNotified ? "success" : isReviewed ? "info" : "warning"}>{pathology.status}</StatusBadge></div><p className="mt-1 font-mono text-[11px] text-muted-foreground">{pathology.accession} · Received {formatInTimeZone(pathology.receivedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</p></div><Button asChild variant="outline" size="sm"><Link href="/patients/sarah-mitchell"><UserRound className="size-3.5" /> Open chart</Link></Button></div>
            <CardContent className="space-y-6 p-5">
              <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_260px]">
                <div><div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.13em] text-muted-foreground"><FlaskConical className="size-3.5" /> Final diagnosis</div><p className="mt-3 text-lg font-semibold leading-7 tracking-[-0.02em]">{data.pathology.diagnosis}</p><Separator className="my-5" /><div className="rounded-lg border border-violet-200 bg-violet-50/50 p-4"><div className="flex items-center gap-2"><Sparkles className="size-4 text-violet-700" /><p className="text-xs font-semibold text-violet-950">Patient-friendly summary · AI proposal</p></div><p className="mt-2 text-sm leading-6 text-violet-950/80">{data.pathology.summary}</p><p className="mt-3 text-[10px] text-violet-800/70">{data.pathology.aiProvenance ? `${data.pathology.aiProvenance.model} · ${data.pathology.aiProvenance.promptVersion} · run ${data.pathology.aiProvenance.aiRunId}` : "No AI provenance was returned for this summary"} · Requires clinician approval</p></div></div>
                <figure><div className="relative aspect-[4/3] overflow-hidden rounded-lg border bg-muted"><Image src={data.patient.lesion.overviewImage.url} alt={`Synthetic clinical photograph linked to ${data.patient.name}’s ${data.patient.lesion.location} pathology result`} fill className="object-cover" sizes="260px" priority /></div><figcaption className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground"><span>{data.pathology.links.find((item) => item.kind === "lesion")?.label} · {data.pathology.links.find((item) => item.kind === "image")?.label}</span><StatusBadge tone="success"><Link2 className="size-3" /> Linked</StatusBadge></figcaption></figure>
              </div>

              <div><p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.13em] text-muted-foreground">Record linkage</p><div className="flex flex-wrap items-center gap-2 text-[10px]">{data.pathology.links.map((item, index, list) => { const Icon = item.kind === "patient" ? UserRound : item.kind === "image" ? ImageIcon : item.kind === "procedure" ? FileCheck2 : item.kind === "specimen" ? Beaker : item.kind === "result" ? Microscope : FlaskConical; return <span key={item.id} className="contents"><span className="flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-2"><Icon className="size-3.5 text-primary" />{item.label}<span className="sr-only"> {item.id}</span></span>{index < list.length - 1 ? <ArrowRight className="size-3 text-muted-foreground" /> : null}</span>; })}</div></div>
            </CardContent>
          </Card>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
            <Card>
              <CardHeader className="border-b pb-3"><SectionHeader title="Close the loop" description="Review each downstream action before recording completion." /></CardHeader>
              <CardContent className="space-y-3 p-4">
                <label className={`flex gap-3 rounded-lg border p-4 ${isNotified || !pathology.patientMessageDraft || !providerCanMutate ? "opacity-60" : "cursor-pointer"}`}><Checkbox checked={isNotified || notifyApproved} disabled={isNotified || !pathology.patientMessageDraft || !providerCanMutate} onCheckedChange={(checked) => setNotifyApproved(checked === true)} /><span className="flex size-8 items-center justify-center rounded-md bg-violet-50 text-violet-700"><MessageSquareText className="size-4" /></span><span className="flex-1"><span className="block text-xs font-semibold">{isNotified ? "Patient communication sent" : pathology.patientMessageDraft ? "Approve patient communication" : "Patient communication unavailable"}</span><span className="mt-1 block text-[11px] leading-4 text-muted-foreground" data-testid="pathology-message-draft">{pathology.patientMessageDraft?.body ?? "No durable patient-message draft was returned; notification is disabled."}</span></span><StatusBadge tone={isNotified ? "success" : pathology.patientMessageDraft ? "ai" : "neutral"}>{isNotified ? "Sent" : pathology.patientMessageDraft ? pathology.patientMessageDraft.status : "No draft"}</StatusBadge></label>
                <label className={`flex gap-3 rounded-lg border p-4 ${followupRecorded || !providerCanMutate ? "opacity-60" : "cursor-pointer"}`}><Checkbox checked={followupRecorded || followupApproved} disabled={followupRecorded || !providerCanMutate} onCheckedChange={(checked) => setFollowupApproved(checked === true)} data-testid="pathology-followup" /><span className="flex size-8 items-center justify-center rounded-md bg-sky-50 text-sky-700"><CalendarCheck2 className="size-4" /></span><span className="flex-1"><span className="block text-xs font-semibold">{followupRecorded ? pathology.followup?.title ?? "Follow-up outreach created" : "Create follow-up outreach"}</span><span className="mt-1 block text-[11px] leading-4 text-muted-foreground">{pathology.followup ? `Task ${pathology.followup.id} is ${pathology.followup.status}; due ${formatInTimeZone(pathology.followup.dueAt, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" })}.` : "Create scheduling outreach and track acceptance or documented deferral."}</span></span><StatusBadge tone={followupRecorded ? "success" : "info"}>{followupRecorded ? pathology.followup?.status ?? "Created" : "Optional"}</StatusBadge></label>
                <div className="flex gap-3 rounded-lg border p-4"><span className="flex size-8 items-center justify-center rounded-md bg-emerald-50 text-emerald-700"><ShieldCheck className="size-4" /></span><span className="flex-1"><span className="block text-xs font-semibold">Resolve pathology safety task</span><span className="mt-1 block text-[11px] leading-4 text-muted-foreground">Closes only after clinical review and a durable patient-notification outcome.</span></span><StatusBadge tone="success">Automatic</StatusBadge></div>
              </CardContent>
            </Card>
            <Card className="h-fit border-primary/25">
              <CardHeader className="pb-3"><SectionHeader title="Record review" action={<StatusBadge tone="warning">Human approval</StatusBadge>} /></CardHeader>
              <CardContent className="space-y-4"><div className="rounded-lg bg-muted/40 p-3 text-xs"><p className="font-semibold">Disposition recorded on approval</p><p className="mt-1 leading-5 text-muted-foreground">The review request records clinical monitoring; patient notification and follow-up are controlled separately above.</p></div><div className="flex items-center justify-between text-xs"><span className="text-muted-foreground">Closure due</span><span className="font-mono">{formatInTimeZone(pathology.closureDueAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span></div>{mode !== "live" ? <Alert className="border-amber-200 bg-amber-50"><AlertTriangle className="size-4 text-amber-700" /><AlertTitle>Read-only preview</AlertTitle><AlertDescription>Review is disabled without durable API connectivity.</AlertDescription></Alert> : null}{submitError ? <Alert variant="destructive"><AlertTitle>Nothing was saved</AlertTitle><AlertDescription>{submitError}</AlertDescription></Alert> : null}{isNotified ? <Alert className="border-emerald-200 bg-emerald-50"><CheckCircle2 className="size-4 text-emerald-700" /><AlertTitle>Closure complete</AlertTitle><AlertDescription>The durable result is reviewed and the patient notification is recorded.</AlertDescription></Alert> : null}{(!isNotified || !followupRecorded) ? <Button className="w-full" size="lg" disabled={mode !== "live" || !providerCanMutate || submitting || (isReviewed && !hasNotificationAction && !hasFollowupAction)} onClick={() => void reviewResult()} data-testid="review-pathology">{!providerCanMutate ? "Provider approval required" : submitting ? "Recording action…" : hasNotificationAction ? isReviewed ? "Notify patient" : "Review & notify" : hasFollowupAction ? isReviewed ? "Create follow-up" : "Review & create follow-up" : isReviewed ? "Select a downstream action" : "Record review"} <Check className="size-4" /></Button> : null}{(isNotified || receipt?.notificationId) ? <Button asChild variant="outline" className="w-full"><Link href="/messages">Open patient message <ArrowRight className="size-4" /></Link></Button> : null}</CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

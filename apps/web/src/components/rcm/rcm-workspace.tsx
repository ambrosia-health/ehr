"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  ReceiptText,
  Send,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader, SectionHeader, StatusBadge } from "@/components/product/page-elements";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest, endpoints } from "@/lib/api/client";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { selectDenialClaim } from "@/lib/api/selectors";
import type { DemoBootstrap, StatusTone } from "@/lib/api/types";
import { formatInTimeZone } from "@/lib/date";

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function claimTone(status: DemoBootstrap["claims"][number]["status"]): StatusTone {
  if (status === "paid" || status === "accepted") return "success";
  if (status === "denied") return "danger";
  if (status === "adjudicated") return "info";
  return "neutral";
}

function metricSignal(score: number | null): string {
  if (score == null) return "Insufficient data";
  if (score >= 100) return "On target";
  if (score >= 70) return "Near target";
  return "Needs action";
}

export function RcmWorkspace() {
  const { data, mode, error, refetch } = useDemoBootstrap();
  if (mode === "loading") return <PageLoading label="Loading revenue cycle" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  if (data.claims.length === 0) return <WorkspaceUnavailable title="Claims are not available for your role" description="Patient and clinical sessions do not receive revenue-cycle records." />;

  const acceptance = data.metrics.find((metric) => metric.id === "accept");
  const denialRate = data.metrics.find((metric) => metric.id === "denial");
  const daysAr = data.metrics.find((metric) => metric.id === "ar");
  const revenueVisit = data.metrics.find((metric) => metric.id === "revenue");
  const workQueue = data.queues.find((queue) => queue.id === "claims");
  const activeDenials = data.claims.filter((claim) => claim.denial?.status === "open");
  const attentionClaims = data.claims.filter((claim) => claim.status === "draft" || claim.status === "denied");
  const atRisk = activeDenials.reduce((sum, claim) => sum + (claim.denial?.recoverable ?? 0), 0);
  const recoveredRevenue = data.claims.reduce((sum, claim) => sum + (claim.denial?.recovery?.recoveredAmount ?? 0), 0);
  const financial = data.financialContext;
  const relatedClaim = data.claims.find((claim) => claim.financialContext.eligibility?.id === financial?.eligibility.id);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Financial operations" title="Revenue cycle" description="Eligibility, documentation, claims, remittance, and patient responsibility remain connected to the clinical source record." />
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Revenue cycle metrics">
        {[acceptance, denialRate, daysAr, revenueVisit].filter(Boolean).map((metric) => <Card key={metric!.id}><CardContent className="p-4"><div className="flex items-start justify-between gap-3"><p className="min-w-0 text-xs font-medium leading-4 text-muted-foreground">{metric!.label}</p><StatusBadge tone={metric!.score == null ? "neutral" : metric!.tone} className="shrink-0">{metricSignal(metric!.score)}</StatusBadge></div><p className="mt-4 font-mono text-2xl font-semibold tracking-[-0.04em]">{metric!.value ?? "N/A"}</p><p className="mt-2 text-[10px] leading-4 text-muted-foreground">Target {metric!.target}</p><p className="mt-1 text-[10px] leading-4 text-muted-foreground">{metric!.supportingCount}</p></CardContent></Card>)}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.65fr)]">
        <Card className="overflow-hidden">
          <CardHeader className="border-b pb-4"><SectionHeader title="Claims requiring attention" description="Only claims with a current action—not already-paid history." action={<StatusBadge tone={attentionClaims.length ? workQueue?.tone : "success"}>{attentionClaims.length} open</StatusBadge>} /></CardHeader>
          <CardContent className="p-0">
            <Table><TableHeader><TableRow><TableHead>Claim</TableHead><TableHead>Patient / payer</TableHead><TableHead className="hidden md:table-cell">Codes</TableHead><TableHead>Amount</TableHead><TableHead>Status</TableHead><TableHead className="w-10"><span className="sr-only">Open</span></TableHead></TableRow></TableHeader><TableBody>{attentionClaims.length === 0 ? <TableRow><TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">No claims require action. Paid and accepted claims remain available in their durable history.</TableCell></TableRow> : null}{attentionClaims.map((claim) => <TableRow key={claim.id}><TableCell className="font-mono text-xs">{claim.claimNumber}</TableCell><TableCell><p className="text-xs font-semibold">{claim.patient}</p><p className="text-[10px] text-muted-foreground">{claim.payer}</p></TableCell><TableCell className="hidden md:table-cell"><div className="flex max-w-44 flex-wrap gap-1">{claim.codes.map((code) => <StatusBadge key={code} className="font-mono text-[9px]">{code}</StatusBadge>)}</div></TableCell><TableCell className="font-mono text-xs">{currency.format(claim.amount)}</TableCell><TableCell><StatusBadge tone={claimTone(claim.status)}>{claim.status}</StatusBadge></TableCell><TableCell><Button asChild variant="ghost" size="icon-sm"><Link href={claim.denial ? "/rcm/denials" : `/rcm/claims/${claim.id}`} aria-label={`Open claim ${claim.claimNumber}`}><ChevronRight /></Link></Button></TableCell></TableRow>)}</TableBody></Table>
          </CardContent>
        </Card>

        <div className="space-y-5">
          {activeDenials.length ? <Card className="border-rose-200 bg-rose-50/35"><CardHeader className="pb-3"><SectionHeader title="Recoverable denial" description={workQueue?.detail} action={<AlertTriangle className="size-4 text-rose-700" />} /></CardHeader><CardContent><p className="font-mono text-3xl font-semibold tracking-[-0.05em] text-rose-950">{currency.format(atRisk)}</p><p className="mt-2 text-xs leading-5 text-rose-950/70">A rules-based correction is available; human approval is required before resubmission.</p><Button asChild className="mt-4" size="sm"><Link href="/rcm/denials">Open denial recovery <ArrowRight className="size-3.5" /></Link></Button></CardContent></Card> : recoveredRevenue > 0 ? <Card className="border-emerald-200 bg-emerald-50/35"><CardHeader className="pb-3"><SectionHeader title="Recovered revenue" action={<CheckCircle2 className="size-4 text-emerald-700" />} /></CardHeader><CardContent><p className="font-mono text-3xl font-semibold tracking-[-0.05em] text-emerald-950">{currency.format(recoveredRevenue)}</p><p className="mt-2 text-xs leading-5 text-emerald-950/70">Paid after corrected-claim review and payer adjudication.</p><Button asChild className="mt-4" size="sm"><Link href="/rcm/denials">View recovery record <ArrowRight className="size-3.5" /></Link></Button></CardContent></Card> : null}
          {financial ? <Card><CardHeader className="pb-3"><SectionHeader title="Featured financial context" action={<StatusBadge tone={financial.eligibility.status === "active" ? "success" : "neutral"}>{financial.eligibility.status}</StatusBadge>} /></CardHeader><CardContent className="space-y-3 text-xs"><div className="flex justify-between"><span className="text-muted-foreground">Plan</span><span className="font-medium">{financial.coverage.payer} {financial.coverage.plan}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Network</span><span>{financial.eligibility.network ?? "Not returned"}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Expected plan payment</span><span className="font-mono">{currency.format(financial.estimate.expectedPlanPayment)}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Estimated patient responsibility</span><span className="font-mono font-semibold">{currency.format(financial.estimate.patientResponsibility)}</span></div>{relatedClaim ? <><Separator /><Button asChild variant="outline" size="sm" className="w-full"><Link href={`/rcm/claims/${relatedClaim.id}`}>Open related claim</Link></Button></> : null}</CardContent></Card> : null}
        </div>
      </div>
    </div>
  );
}

export function ClaimDetail({ claimId }: { claimId: string }) {
  const { data, mode, error, refetch } = useDemoBootstrap();
  if (mode === "loading") return <PageLoading label="Loading claim" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  const claim = data.claims.find((item) => item.id === claimId);
  if (!claim) return <WorkspaceUnavailable title="This claim is not available for your role" />;
  const completedEvents = claim.events.filter((event) => event.complete).length;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Claim detail" title={claim.claimNumber} description={`${claim.patient} · ${claim.payer} · Durable claim and clearinghouse record`} actions={<><Button asChild variant="outline"><Link href="/rcm"><ArrowLeft className="size-4" /> Revenue cycle</Link></Button><span data-testid="claim-status" data-status={claim.status}><StatusBadge tone={claimTone(claim.status)}>{claim.status}</StatusBadge></span></>} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <Card><CardHeader className="border-b pb-3"><SectionHeader title="Claim lifecycle" description={`${completedEvents} of ${claim.events.length} payer events complete`} /></CardHeader><CardContent className="overflow-x-auto p-5"><div className="flex min-w-[680px] items-start">{claim.events.map((event, index) => <div key={event.label} className="relative flex flex-1 flex-col items-center text-center" data-testid="claim-event" data-complete={event.complete ? "true" : "false"}><div className={`z-10 flex size-8 items-center justify-center rounded-full border-2 ${event.complete ? "border-emerald-600 bg-emerald-600 text-white" : "border-border bg-background text-muted-foreground"}`}>{event.complete ? <Check className="size-4" /> : <Clock3 className="size-3.5" />}</div>{index < claim.events.length - 1 ? <div className={`absolute left-1/2 right-[-50%] top-4 h-0.5 ${claim.events[index + 1]?.complete ? "bg-emerald-500" : "bg-border"}`} /> : null}<p className="mt-2 text-[11px] font-semibold">{event.label}</p><p className="mt-1 font-mono text-[9px] text-muted-foreground">{formatInTimeZone(event.at, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</p></div>)}</div></CardContent></Card>
          <Card><CardHeader className="border-b pb-3"><SectionHeader title="Claim lines" description="Charges, allowed amounts, and payments returned by the durable claim read model." /></CardHeader><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>Line / code</TableHead><TableHead>Diagnoses</TableHead><TableHead>Units</TableHead><TableHead>Charge</TableHead><TableHead>Allowed</TableHead><TableHead>Paid</TableHead></TableRow></TableHeader><TableBody>{claim.lines.map((line) => <TableRow key={line.id}><TableCell><p className="font-mono text-xs font-semibold">{line.lineNumber} · {line.procedureCode}</p><p className="font-mono text-[9px] text-muted-foreground">{line.id}</p></TableCell><TableCell className="font-mono text-xs">{line.diagnosisCodes.join(", ")}</TableCell><TableCell className="font-mono text-xs">{line.units}</TableCell><TableCell className="font-mono text-xs">{currency.format(line.charge)}</TableCell><TableCell className="font-mono text-xs">{currency.format(line.allowed)}</TableCell><TableCell className="font-mono text-xs">{currency.format(line.paid)}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>
          <Card><CardHeader className="border-b pb-3"><SectionHeader title="Payments" description={`${claim.payments.length} durable payment record${claim.payments.length === 1 ? "" : "s"}`} /></CardHeader><CardContent className="space-y-2 p-4">{claim.payments.length ? claim.payments.map((payment) => <div key={payment.id} className="grid gap-2 rounded-lg border p-3 text-xs sm:grid-cols-[1fr_auto]"><div><p className="font-semibold">{payment.source} · {payment.method ?? "Method not returned"}</p><p className="mt-1 font-mono text-[10px] text-muted-foreground">{payment.reference ?? payment.id} · {formatInTimeZone(payment.receivedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</p></div><div className="text-right"><p className="font-mono font-semibold">{currency.format(payment.amount)}</p><StatusBadge tone={payment.status === "settled" ? "success" : "neutral"}>{payment.status}</StatusBadge></div></div>) : <p className="text-xs text-muted-foreground">No payment has been recorded for this claim.</p>}</CardContent></Card>
        </div>
        <aside className="space-y-5"><Card><CardHeader className="pb-3"><SectionHeader title="Financial summary" /></CardHeader><CardContent className="space-y-3 text-xs"><div className="flex justify-between"><span className="text-muted-foreground">Total charges</span><span className="font-mono font-semibold">{currency.format(claim.amount)}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Allowed</span><span className="font-mono">{currency.format(claim.allowed)}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Paid</span><span className="font-mono text-emerald-700">{currency.format(claim.paid)}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Remaining allowed balance</span><span className="font-mono">{currency.format(claim.remainingBalance)}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Patient responsibility</span><span className="font-mono">{currency.format(claim.patientResponsibility)}</span></div>{claim.balance ? <div className="flex justify-between"><span className="text-muted-foreground">Patient balance</span><span className="font-mono">{currency.format(claim.balance.currentBalance)} · {claim.balance.status}</span></div> : null}<div className="flex justify-between"><span className="text-muted-foreground">Payer</span><span>{claim.payer}</span></div><Separator /><div className="flex justify-between"><span className="text-muted-foreground">Current status</span><StatusBadge tone={claimTone(claim.status)}>{claim.status}</StatusBadge></div></CardContent></Card><Card><CardHeader className="pb-3"><SectionHeader title="Claim provenance" action={<ShieldCheck className="size-4 text-primary" />} /></CardHeader><CardContent><p className="text-xs leading-5 text-muted-foreground">{claim.provenance.source.replaceAll("_", " ")}</p><p className="mt-2 break-all font-mono text-[10px] text-muted-foreground">Latest event: {claim.provenance.latestEventId ?? "none"}</p></CardContent></Card></aside>
      </div>
    </div>
  );
}

interface ResubmitReceipt {
  claimId: string;
  claimEventId: string;
  status: string;
  submittedAt: string;
  assignedTaskId?: string;
}

export function DenialRecovery() {
  const { data, mode, error, refetch } = useDemoBootstrap();
  const queryClient = useQueryClient();
  const [appeal, setAppeal] = useState("");
  const [receipt, setReceipt] = useState<ResubmitReceipt | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  if (mode === "loading") return <PageLoading label="Loading denial recovery" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  const claim = selectDenialClaim(data.claims);
  if (!claim?.denial) return <WorkspaceUnavailable title="No authorized denial is available" />;
  const denial = claim.denial;
  const appealBody = appeal || denial.appealDraft;
  const claimId = claim.id;
  const denialOpen = denial.status === "open";
  const recovery = denial.recovery;
  const recovered = Boolean(recovery && (recovery.outcome === "paid" || recovery.recoveredAmount > 0));

  async function resubmit() {
    if (mode !== "live") return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const nextReceipt = await apiRequest<ResubmitReceipt>(endpoints.denialResubmit(claimId), { method: "POST", body: { appealBody, correction: denial.recommendation, sourceTaskId: denial.assignedTaskId } });
      setReceipt(nextReceipt);
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
    } catch (resubmitError) {
      setSubmitError(resubmitError instanceof Error ? resubmitError.message : "The corrected claim could not be resubmitted.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Denial recovery" title={`${claim.claimNumber} · ${claim.patient}`} description={recovered ? `${claim.payer} · ${claim.denial.code} · ${currency.format(recovery!.recoveredAmount)} recovered` : `${claim.payer} · ${claim.denial.code} · ${currency.format(claim.denial.recoverable)} ${denialOpen ? "recoverable" : "submitted for recovery"}`} actions={<><Button asChild variant="outline"><Link href="/rcm"><ArrowLeft className="size-4" /> Revenue cycle</Link></Button><StatusBadge tone={recovered ? "success" : denialOpen ? "danger" : "info"}>{recovered ? "recovered" : denial.status}</StatusBadge></>} />
      {receipt ? <Alert className="border-emerald-200 bg-emerald-50" data-testid="denial-resubmit-receipt"><CheckCircle2 className="size-4 text-emerald-700" /><AlertTitle>Corrected claim {receipt.status}</AlertTitle><AlertDescription>{receipt.claimId} · event {receipt.claimEventId} · {formatInTimeZone(receipt.submittedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })} · task {receipt.assignedTaskId ?? "closed by workflow"}</AlertDescription></Alert> : null}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <Card className={denialOpen ? "border-rose-200" : "border-sky-200"}><CardHeader className={`border-b pb-3 ${denialOpen ? "bg-rose-50/45" : "bg-sky-50/45"}`}><SectionHeader title="Denial classified" description={claim.denial.code} action={<StatusBadge tone={denialOpen ? "danger" : "info"}>{denial.status}</StatusBadge>} /></CardHeader><CardContent className="space-y-4 p-5"><div><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Payer reason</p><p className="mt-2 text-sm font-semibold">{claim.denial.reason}</p></div><div className="rounded-lg border bg-muted/30 p-4"><div className="flex items-center gap-2"><ShieldCheck className="size-4 text-primary" /><p className="text-xs font-semibold">Recommended correction · {denial.recommendationSource.replaceAll("_", " ")}</p></div><p className="mt-2 text-xs leading-5 text-muted-foreground">{claim.denial.recommendation}</p></div></CardContent></Card>
          <Card><CardHeader className="border-b pb-3"><SectionHeader title={denialOpen ? "Draft appeal" : "Submitted appeal"} description="Returned by the denial workflow; source-level links are not expanded in this read model." action={<StatusBadge tone={denialOpen ? "neutral" : "info"}>{recovery?.status ?? "draft"}</StatusBadge>} /></CardHeader><CardContent className="p-5"><Textarea value={appealBody} onChange={(event) => setAppeal(event.target.value)} readOnly={!denialOpen} className="min-h-52 text-sm leading-6" aria-label="Draft denial appeal" /><p className="mt-2 text-[10px] text-muted-foreground">{denialOpen ? "Edits are submitted with the corrected claim; the source note remains unchanged." : `Appeal ${recovery?.appealId ?? "record"} was submitted ${recovery?.submittedAt ? formatInTimeZone(recovery.submittedAt, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "without a recorded timestamp"}.`}</p></CardContent></Card>
        </div>
        <aside className="space-y-5"><Card><CardHeader className="pb-3"><SectionHeader title="Recovery inputs" /></CardHeader><CardContent className="space-y-3">{[{ icon: FileText, label: "Appeal draft", detail: denial.appealDraft ? "Returned by denial workflow" : "No appeal draft returned" }, { icon: ReceiptText, label: "Correction instruction", detail: denial.recommendation }, { icon: UserRound, label: "Assigned task", detail: denial.assignedTaskId }].map((item) => { const Icon = item.icon; return <div key={item.label} className="flex gap-3 rounded-lg border p-3"><Icon className="mt-0.5 size-4 shrink-0 text-primary" /><div><p className="text-xs font-semibold">{item.label}</p><p className="text-[10px] leading-4 text-muted-foreground">{item.detail}</p></div></div>; })}</CardContent></Card>{denialOpen ? <Card className="border-primary/25"><CardHeader className="pb-3"><SectionHeader title="Approve resubmission" /></CardHeader><CardContent className="space-y-4"><div className="flex justify-between text-xs"><span className="text-muted-foreground">Recoverable amount</span><span className="font-mono text-lg font-semibold">{currency.format(claim.denial.recoverable)}</span></div>{mode !== "live" ? <Alert className="border-amber-200 bg-amber-50"><AlertTriangle className="size-4 text-amber-700" /><AlertDescription>Resubmission requires the domain API.</AlertDescription></Alert> : null}{submitError ? <Alert variant="destructive"><AlertTitle>Nothing was submitted</AlertTitle><AlertDescription>{submitError}</AlertDescription></Alert> : null}<Button className="w-full" size="lg" onClick={() => void resubmit()} disabled={mode !== "live" || submitting || Boolean(receipt)} data-testid="resubmit-claim">{receipt ? "Resubmitted" : submitting ? "Submitting…" : "Approve & resubmit"} <Send className="size-4" /></Button></CardContent></Card> : <Card className={recovered ? "border-emerald-200 bg-emerald-50/35" : "border-sky-200 bg-sky-50/35"} data-testid="denial-recovery-status" data-claim-status={claim.status}><CardHeader className="pb-3"><SectionHeader title={recovered ? "Revenue recovered" : "Payer response pending"} /></CardHeader><CardContent className="space-y-3"><p className="font-mono text-3xl font-semibold">{currency.format(recovery?.recoveredAmount ?? 0)}</p><div className="flex items-center justify-between text-xs"><span className="text-muted-foreground">Claim status</span><StatusBadge tone={claimTone(claim.status)}>{claim.status}</StatusBadge></div><div className="flex items-center justify-between text-xs"><span className="text-muted-foreground">Appeal outcome</span><StatusBadge tone={recovered ? "success" : "info"}>{recovery?.outcome ?? recovery?.status ?? "submitted"}</StatusBadge></div>{!recovered ? <p className="text-[10px] leading-4 text-muted-foreground">Use the protected presenter claim response to advance this resubmitted claim through payer adjudication.</p> : null}</CardContent></Card>}</aside>
      </div>
    </div>
  );
}

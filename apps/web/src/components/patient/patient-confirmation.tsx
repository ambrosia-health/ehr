"use client";

import { AlertTriangle, ArrowRight, CalendarCheck2, Check, Clock3, MapPin, MessageSquareText, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/product/page-elements";
import { useDemoSession } from "@/components/system/app-providers";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { formatInTimeZone } from "@/lib/date";

export function PatientConfirmation() {
  const { intakeTriage } = useDemoSession();
  const { data, mode, error, refetch } = useDemoBootstrap();
  if (mode === "loading") return <div className="mx-auto max-w-4xl px-4 py-10"><PageLoading label="Confirming your appointment" /></div>;
  if (!data) return <div className="mx-auto max-w-4xl px-4 py-10"><PageError error={error} retry={refetch} /></div>;
  if (!data.intake || !data.patient) return <div className="mx-auto max-w-4xl px-4 py-10"><WorkspaceUnavailable title="Appointment details are not available for this role" /></div>;
  const intake = data.intake;
  const patient = data.patient;
  const triage = intake.triage ?? intakeTriage;
  const appointment = intake.bookedAppointment;
  if (!appointment) return <div className="mx-auto max-w-4xl px-4 py-10"><WorkspaceUnavailable title="No confirmed appointment is available" description="Complete the patient intake to create a durable appointment confirmation." /></div>;
  const eligibility = intake.eligibility;
  const estimate = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(eligibility.estimatedResponsibility);
  const appointmentTime = formatInTimeZone(appointment.startsAt, data.organization.timezone, { weekday: "long", month: "long", day: "numeric", hour: "numeric", minute: "2-digit" });

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-12">
      <div className="mt-5 text-center">
        <span className="mx-auto flex size-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><Check className="size-7" /></span>
        <StatusBadge tone="success" className="mt-5">Appointment confirmed</StatusBadge>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">You’re all set, {patient.name.split(" ")[0]}.</h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted-foreground">{appointment.provider} already has your intake, photograph, medication list, and insurance response.</p>
      </div>
      {triage ? <Alert className={`mx-auto mt-6 max-w-2xl ${triage.status === "staff_review" ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`} data-testid="intake-triage-receipt">{triage.status === "staff_review" ? <AlertTriangle className="size-4 text-amber-700" /> : <ShieldCheck className="size-4 text-emerald-700" />}<AlertTitle>{triage.status === "staff_review" ? "Clinical review queued" : "Safety check recorded"}</AlertTitle><AlertDescription>{triage.status === "staff_review" ? `The care team received task ${triage.taskId ?? "pending assignment"} and notification ${triage.notificationId ?? "pending"}. Readiness: ${triage.readinessStatus.replaceAll("_", " ")}.` : `Your explicit response was recorded as routine. Readiness: ${triage.readinessStatus.replaceAll("_", " ")}.`}</AlertDescription></Alert> : null}
      <Card className="mx-auto mt-8 max-w-2xl overflow-hidden shadow-sm">
        <div className="bg-primary px-6 py-5 text-primary-foreground"><p className="text-xs font-semibold uppercase tracking-[0.15em] text-primary-foreground/65">Changing lesion consultation</p><p className="mt-1 text-xl font-semibold">{appointmentTime}</p></div>
        <CardContent className="divide-y p-0">
          <div className="grid gap-4 p-5 sm:grid-cols-2"><div className="flex gap-3"><CalendarCheck2 className="mt-0.5 size-4 text-primary" /><div><p className="text-sm font-semibold">{appointment.provider}</p><p className="text-xs text-muted-foreground">Board-certified dermatologist</p></div></div><div className="flex gap-3"><MapPin className="mt-0.5 size-4 text-primary" /><div><p className="text-sm font-semibold">{appointment.location}</p><p className="text-xs text-muted-foreground">In-person dermatology clinic</p></div></div></div>
          <div className="p-5"><p className="text-sm font-semibold">Before you arrive</p><ul className="mt-3 space-y-2 text-xs text-muted-foreground">{intake.preparation.map((instruction, index) => <li key={instruction} className="flex gap-2">{index === intake.preparation.length - 1 ? <Clock3 className="size-3.5 text-primary" /> : <Check className="size-3.5 text-emerald-600" />}{instruction}</li>)}</ul></div>
          <div className="flex flex-col gap-3 bg-muted/30 p-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="flex items-center gap-2 text-xs font-semibold"><ShieldCheck className="size-3.5 text-primary" /> Eligibility {eligibility.status.toLowerCase()}</p><p className="mt-1 text-xs text-muted-foreground">Estimated responsibility: <span className="font-mono font-medium text-foreground">{estimate}</span></p></div><Button asChild variant="outline"><Link href="/messages"><MessageSquareText className="size-4" /> Message care team</Link></Button></div>
        </CardContent>
      </Card>
      {data.session.presenter ? <div className="mx-auto mt-6 flex max-w-2xl flex-col gap-3 rounded-lg border border-violet-200 bg-violet-50 p-4 sm:flex-row sm:items-center"><Sparkles className="size-5 shrink-0 text-violet-700" /><p className="flex-1 text-xs leading-5 text-violet-950">For the demo: choose the next chapter so Ambrosia can activate the required protected staff persona.</p><Button asChild size="sm"><Link href="/presenter">Open presenter console <ArrowRight className="size-3.5" /></Link></Button></div> : null}
    </div>
  );
}

"use client";

import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  ListChecks,
  MessageSquareText,
  Search,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader, SectionHeader, StatusBadge } from "@/components/product/page-elements";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDemoBootstrap } from "@/lib/api/hooks";
import type { StatusTone } from "@/lib/api/types";
import { formatInTimeZone } from "@/lib/date";

function readinessTone(value: number): StatusTone {
  if (value >= 90) return "success";
  if (value >= 75) return "info";
  return "warning";
}

export function CommandCenter() {
  const { data, mode, error, refetch } = useDemoBootstrap();
  const [scheduleQuery, setScheduleQuery] = useState("");
  if (mode === "loading") return <PageLoading label="Preparing today’s command center" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  if (!data.commandCenter) return <WorkspaceUnavailable title="The command center is not available for your role" />;

  const stats = data.commandCenter;
  const scenarioDate = formatInTimeZone(data.scenario.currentTime, data.organization.timezone, { weekday: "long", month: "long", day: "numeric" });
  const activePersona = data.personas.find((item) => item.id === data.session.persona) ?? data.personas.find((item) => item.id === "provider");
  const familyHistory = data.patient?.problems.find((problem) => problem.toLowerCase().includes("family history")) ?? "Family history reviewed";
  const normalizedScheduleQuery = scheduleQuery.trim().toLowerCase();
  const filteredSchedule = data.schedule.filter((appointment) => !normalizedScheduleQuery || [appointment.patient, appointment.visit, appointment.provider].some((value) => value.toLowerCase().includes(normalizedScheduleQuery)));
  const patientAppointment = data.patient ? data.schedule.find((appointment) => appointment.patient === data.patient?.name) : undefined;
  const ownerAggregate = data.session.persona === "owner";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={scenarioDate}
        title={`Good morning, ${activePersona?.name.replace(/^Dr\.\s*/, "").split(" ")[0] ?? "care team"}.`}
        description={`${stats.scheduledVisits} visits are scheduled. The care team has prioritized the work that must be resolved before the next patient arrives.`}
        actions={<><Button asChild variant="outline"><a href="#today-schedule"><Search className="size-4" /> Find patient</a></Button><Button asChild><a href="#today-schedule"><CalendarDays className="size-4" /> Today’s schedule</a></Button></>}
      />

      <section aria-label="Today at a glance" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card><CardContent className="p-4"><div className="flex items-center justify-between"><span className="flex size-8 items-center justify-center rounded-md bg-primary/8 text-primary"><CalendarDays className="size-4" /></span><StatusBadge tone="neutral">Current schedule</StatusBadge></div><p className="mt-4 font-mono text-2xl font-semibold tracking-[-0.04em]">{stats.scheduledVisits}</p><p className="text-xs font-medium">Scheduled visits</p><p className="mt-1 text-[11px] text-muted-foreground">{stats.completedVisits} completed · {stats.inProgressVisits} in progress</p></CardContent></Card>
        <Card><CardContent className="p-4"><div className="flex items-center justify-between"><span className="flex size-8 items-center justify-center rounded-md bg-emerald-50 text-emerald-700"><UserRoundCheck className="size-4" /></span><span className="font-mono text-[11px] text-muted-foreground">Today</span></div><p className="mt-4 font-mono text-2xl font-semibold tracking-[-0.04em]">{stats.readinessPercent}%</p><p className="text-xs font-medium">Patient readiness</p><Progress value={stats.readinessPercent} className="mt-2 h-1.5" /></CardContent></Card>
        <Card><CardContent className="p-4"><div className="flex items-center justify-between"><span className="flex size-8 items-center justify-center rounded-md bg-violet-50 text-violet-700"><Clock3 className="size-4" /></span><StatusBadge tone="ai">AI-assisted</StatusBadge></div><p className="mt-4 font-mono text-2xl font-semibold tracking-[-0.04em]">{stats.medianSignMinutes}m</p><p className="text-xs font-medium">Median time to sign</p><p className="mt-1 text-[11px] text-muted-foreground">{stats.signMinutesImprovement > 0 ? `${stats.signMinutesImprovement} minutes faster this month` : "Current-period baseline"}</p></CardContent></Card>
        <Card><CardContent className="p-4"><div className="flex items-center justify-between"><span className="flex size-8 items-center justify-center rounded-md bg-amber-50 text-amber-700"><ShieldCheck className="size-4" /></span><StatusBadge tone={stats.pathologyDueToday ? "warning" : "neutral"}>{stats.pathologyDueToday} awaiting review</StatusBadge></div><p className="mt-4 font-mono text-2xl font-semibold tracking-[-0.04em]">{stats.pathologyClosurePercent}%</p><p className="text-xs font-medium">Pathology results closed</p><p className="mt-1 text-[11px] text-muted-foreground">{data.queues.find((queue) => queue.id === "path")?.count ?? 0} results remain open</p></CardContent></Card>
      </section>

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.55fr)_minmax(340px,0.75fr)]">
        <Card className="scroll-mt-20 overflow-hidden" id="today-schedule">
          <CardHeader className="border-b pb-4"><SectionHeader title="Today’s schedule" description="Authorized providers and locations" action={<div className="relative hidden sm:block"><Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" /><Input aria-label="Filter schedule" className="h-8 w-48 pl-8 text-xs" placeholder="Patient, visit, provider" value={scheduleQuery} onChange={(event) => setScheduleQuery(event.target.value)} /></div>} /></CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader><TableRow><TableHead className="w-20">Time</TableHead><TableHead>Patient</TableHead><TableHead className="hidden md:table-cell">Visit</TableHead><TableHead className="hidden lg:table-cell">Readiness</TableHead><TableHead>Status</TableHead><TableHead className="w-10"><span className="sr-only">Open</span></TableHead></TableRow></TableHeader>
              <TableBody>
                {filteredSchedule.length === 0 ? <TableRow><TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">{data.schedule.length === 0 ? ownerAggregate ? "Named schedules are hidden in aggregate owner view." : "No visits are scheduled for this scenario date." : "No appointments match this filter."}</TableCell></TableRow> : null}
                {filteredSchedule.map((appointment) => {
                  const isFeaturedPatient = Boolean(data.patient && appointment.patient === data.patient.name);
                  return (
                    <TableRow key={appointment.id} className={isFeaturedPatient ? "bg-primary/[0.035]" : undefined}>
                      <TableCell className="font-mono text-xs">{appointment.time}</TableCell>
                      <TableCell><div className="flex items-center gap-3"><Avatar className="size-8"><AvatarFallback className={isFeaturedPatient ? "bg-primary text-primary-foreground" : "bg-muted text-[10px]"}>{appointment.patient.split(" ").map((part) => part[0]).join("")}</AvatarFallback></Avatar><div><p className="text-xs font-semibold">{appointment.patient}</p><div className="mt-1 flex gap-1">{appointment.flags.slice(0, 1).map((flag) => <StatusBadge key={flag} tone={flag === "AI summary" ? "ai" : "warning"} className="h-4 px-1.5 text-[9px]">{flag}</StatusBadge>)}</div></div></div></TableCell>
                      <TableCell className="hidden text-xs md:table-cell"><p>{appointment.visit}</p><p className="text-[10px] text-muted-foreground">{appointment.provider}</p></TableCell>
                      <TableCell className="hidden lg:table-cell"><div className="flex items-center gap-2"><Progress value={appointment.readiness} className="h-1.5 w-16" /><StatusBadge tone={readinessTone(appointment.readiness)} className="h-4 px-1.5 font-mono text-[9px]">{appointment.readiness}%</StatusBadge></div></TableCell>
                      <TableCell><StatusBadge tone={appointment.status === "Arrived" || appointment.status === "Roomed" ? "success" : "neutral"}>{appointment.status}</StatusBadge></TableCell>
                      <TableCell>{isFeaturedPatient ? <Button asChild variant="ghost" size="icon-sm" aria-label={`Open ${appointment.patient}`}><Link href="/patients/sarah-mitchell"><ChevronRight /></Link></Button> : <Button variant="ghost" size="icon-sm" aria-label={`Open ${appointment.patient}`} disabled><ChevronRight /></Button>}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <div className="space-y-5">
          {data.patient && data.encounter ? <Card className="border-violet-200/80 bg-violet-50/35">
            <CardHeader className="pb-3"><SectionHeader title={`${data.patient.name} is ready for you`} description={`${patientAppointment?.time ?? "Scheduled"} · ${patientAppointment?.visit ?? data.patient.lesion.label}`} action={<StatusBadge tone="ai"><Sparkles className="size-3" /> AI pre-visit</StatusBadge>} /></CardHeader>
            <CardContent>
              <p className="text-xs leading-5 text-foreground/85">{data.encounter.previsitSummary}</p>
              <div className="mt-4 grid grid-cols-3 gap-2 border-y border-violet-200/60 py-3 text-center"><div><p className="font-mono text-sm font-semibold">{formatInTimeZone(data.patient.lesion.firstObserved, data.organization.timezone, { month: "short", year: "numeric" })}</p><p className="text-[10px] text-muted-foreground">First observed</p></div><div><p className="font-mono text-sm font-semibold">{data.patient.lesion.dimensions}</p><p className="text-[10px] text-muted-foreground">Dimensions</p></div><div><p className="truncate px-1 text-xs font-semibold">{familyHistory}</p><p className="text-[10px] text-muted-foreground">Risk context</p></div></div>
              <div className="mt-4 flex gap-2"><Button asChild size="sm" data-testid="open-sarah-encounter"><Link href="/encounters/sarah-biopsy"><BrainCircuit className="size-3.5" /> Open encounter</Link></Button><Button asChild variant="outline" size="sm"><Link href="/patients/sarah-mitchell">View chart</Link></Button></div>
            </CardContent>
          </Card> : <Card><CardHeader className="pb-3"><SectionHeader title="Aggregate view" description="Patient-level schedules and clinical records are excluded from the owner session." /></CardHeader><CardContent><p className="text-xs leading-5 text-muted-foreground">Switch to an authorized clinical persona to open a named chart or encounter.</p></CardContent></Card>}

          <Card>
            <CardHeader className="pb-3"><SectionHeader title="Work queues" description="Prioritized by clinical and financial risk" /></CardHeader>
            <CardContent className="space-y-1 p-3 pt-0">
              {data.queues.slice(0, 5).map((queue) => (
                ownerAggregate ? <div key={queue.id} className="flex items-center gap-3 rounded-md p-2.5">
                  <span className="flex size-8 items-center justify-center rounded-md bg-muted text-muted-foreground">{queue.id === "claims" ? <AlertTriangle className="size-4" /> : queue.id === "messages" ? <MessageSquareText className="size-4" /> : queue.id === "path" ? <ClipboardCheck className="size-4" /> : <ListChecks className="size-4" />}</span>
                  <span className="min-w-0 flex-1"><span className="block text-xs font-semibold">{queue.label}</span><span className="block text-[10px] text-muted-foreground">{queue.detail}</span></span>
                  <StatusBadge tone={queue.tone} className="font-mono">{queue.count}</StatusBadge>
                </div> : <Link key={queue.id} href={queue.href} className="flex items-center gap-3 rounded-md p-2.5 hover:bg-muted/60">
                  <span className="flex size-8 items-center justify-center rounded-md bg-muted text-muted-foreground">{queue.id === "claims" ? <AlertTriangle className="size-4" /> : queue.id === "messages" ? <MessageSquareText className="size-4" /> : queue.id === "path" ? <ClipboardCheck className="size-4" /> : <ListChecks className="size-4" />}</span>
                  <span className="min-w-0 flex-1"><span className="block text-xs font-semibold">{queue.label}</span><span className="block text-[10px] text-muted-foreground">{queue.detail}</span></span>
                  <StatusBadge tone={queue.tone} className="font-mono">{queue.count}</StatusBadge>
                </Link>
              ))}
              {ownerAggregate ? <Button asChild variant="ghost" size="sm" className="mt-2 w-full"><Link href="/mso">Open performance intelligence <ArrowRight className="size-3.5" /></Link></Button> : <Button asChild variant="ghost" size="sm" className="mt-2 w-full"><Link href="/messages">Open patient messages <ArrowRight className="size-3.5" /></Link></Button>}
            </CardContent>
          </Card>
        </div>
      </div>

      <section className="grid gap-3 md:grid-cols-3" aria-label="Operational signals">
        <Card><CardContent className="flex items-center gap-4 p-4"><span className="flex size-9 items-center justify-center rounded-md bg-emerald-50 text-emerald-700"><CheckCircle2 className="size-4" /></span><div><p className="text-xs font-semibold">Eligibility clean</p><p className="text-[11px] text-muted-foreground">{stats.eligibilityVerified} of {stats.scheduledVisits} visits verified</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-4 p-4"><span className="flex size-9 items-center justify-center rounded-md bg-violet-50 text-violet-700"><Sparkles className="size-4" /></span><div><p className="text-xs font-semibold">{stats.summariesPrepared} summaries prepared</p><p className="text-[11px] text-muted-foreground">{stats.summaryMinutesSaved > 0 ? `Estimated ${stats.summaryMinutesSaved} minutes saved` : "Current-period baseline"}</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-4 p-4"><span className="flex size-9 items-center justify-center rounded-md bg-sky-50 text-sky-700"><ClipboardCheck className="size-4" /></span><div><p className="text-xs font-semibold">AI-supported notes</p><p className="text-[11px] text-muted-foreground">{stats.documentationSupportPercent}% of notes include recorded AI support</p></div></CardContent></Card>
      </section>
    </div>
  );
}

"use client";

import {
  Beaker,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  EllipsisVertical,
  ExternalLink,
  FileText,
  Flag,
  MessageSquareText,
  Pill,
  ShieldAlert,
  Stethoscope,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { StatusBadge } from "@/components/product/page-elements";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDemoBootstrap } from "@/lib/api/hooks";
import type { DemoBootstrap, StatusTone } from "@/lib/api/types";
import { formatInTimeZone } from "@/lib/date";

type Appointment = DemoBootstrap["schedule"][number];
type Patient = NonNullable<DemoBootstrap["patient"]>;
type Encounter = NonNullable<DemoBootstrap["encounter"]>;
type Pathology = DemoBootstrap["pathology"];

function readinessTone(value: number): StatusTone {
  if (value >= 90) return "success";
  if (value >= 75) return "info";
  return "warning";
}

function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function scheduleMinuteValue(time?: string) {
  if (!time) return null;
  const [hourValue, minuteValue = "0"] = time.split(":");
  let hour = Number(hourValue);
  const minute = Number(minuteValue);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null;
  if (hour < 8) hour += 12;
  return hour * 60 + minute;
}

function openScheduleSlots(afterTime?: string) {
  const appointmentMinutes = scheduleMinuteValue(afterTime);
  if (appointmentMinutes === null) return [];

  const slots: string[] = [];
  for (let value = appointmentMinutes + 30; value <= 17 * 60; value += 30) {
    const slotHour = Math.floor(value / 60);
    const slotMinute = value % 60;
    const displayHour = slotHour > 12 ? slotHour - 12 : slotHour;
    slots.push(`${displayHour}:${slotMinute.toString().padStart(2, "0")}`);
  }
  return slots;
}

function ScheduleRail({
  appointments,
  featuredPatientName,
  ownerAggregate,
  query,
  scheduledVisits,
}: {
  appointments: Appointment[];
  featuredPatientName?: string;
  ownerAggregate: boolean;
  query: string;
  scheduledVisits: number;
}) {
  const latestAppointment = appointments.reduce<Appointment | undefined>((latest, appointment) => {
    if (!latest) return appointment;
    return (scheduleMinuteValue(latest.time) ?? 0) > (scheduleMinuteValue(appointment.time) ?? 0) ? latest : appointment;
  }, undefined);
  const emptySlots = openScheduleSlots(latestAppointment?.time);

  return (
    <aside className="order-2 border-t bg-background px-3 py-6 xl:order-none xl:col-start-1 xl:row-start-1 xl:min-h-[calc(100vh-4.5rem)] xl:border-r xl:border-t-0" aria-label="Today’s schedule">
      <div className="px-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Today · {scheduledVisits} scheduled</p>
        {query ? <p className="mt-2 text-xs text-muted-foreground">Filtered by “{query}”</p> : null}
      </div>

      <div className="mt-7 space-y-2">
        {appointments.length === 0 ? <div className="rounded-lg border border-dashed px-3 py-5 text-center text-xs leading-5 text-muted-foreground">
          {ownerAggregate ? "Named schedules are hidden in aggregate owner view." : query ? "No appointments match this search." : "No visits are scheduled for this scenario date."}
        </div> : appointments.map((appointment) => {
          const featured = appointment.patient === featuredPatientName;
          return featured ? <Link
            key={appointment.id}
            href="/patients/sarah-mitchell"
            className="group block rounded-lg border bg-card px-3 py-3 shadow-[inset_3px_0_0_var(--primary)] transition-colors hover:bg-accent/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`Open ${appointment.patient} chart`}
          >
            <div className="flex items-start justify-between gap-2">
              <span className="font-mono text-xs font-medium tabular-nums">{appointment.time}</span>
              <ChevronRight className="mt-0.5 size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
            </div>
            <div className="mt-3 flex items-center gap-2.5">
              <Avatar className="size-9"><AvatarFallback className="bg-primary text-xs font-semibold text-primary-foreground">{initials(appointment.patient)}</AvatarFallback></Avatar>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{appointment.patient}</p>
                <p className="truncate text-[11px] text-muted-foreground">{appointment.visit}</p>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2 text-xs font-medium text-emerald-700">
              <CheckCircle2 className="size-4" />
              <span>{appointment.readiness}% ready</span>
            </div>
          </Link> : <div key={appointment.id} className="rounded-lg border bg-card px-3 py-3">
            <div className="flex items-center justify-between gap-3"><span className="font-mono text-xs">{appointment.time}</span><StatusBadge tone={readinessTone(appointment.readiness)}>{appointment.readiness}%</StatusBadge></div>
            <p className="mt-2 text-sm font-semibold">{appointment.patient}</p>
            <p className="text-[11px] text-muted-foreground">{appointment.visit}</p>
          </div>;
        })}
      </div>

      {!query && appointments.length > 0 ? <div className="mt-5" aria-label="Open schedule times">
        {emptySlots.map((slot) => <div key={slot} className="border-b py-2.5 first:border-t">
          <p className="font-mono text-[11px] tabular-nums text-muted-foreground">{slot}</p>
          <span className="mt-1 block text-[10px] text-muted-foreground/60" aria-label={`${slot} open`}>—</span>
        </div>)}
        <div className="mt-5 flex items-start gap-2 text-muted-foreground">
          <Flag className="mt-0.5 size-3.5" />
          <div><p className="text-xs font-medium text-foreground">End of day</p><p className="text-[11px]">No more visits</p></div>
        </div>
      </div> : null}
    </aside>
  );
}

function OverviewTab({ patient, timezone }: { patient: Patient; timezone: string }) {
  const lesionStatus = patient.lesion.status.replaceAll("_", " ");

  return (
    <div className="space-y-8 py-8">
      <section className="grid gap-6 md:grid-cols-[minmax(0,1fr)_180px] md:items-start">
        <div>
          <h2 className="text-sm font-semibold">Lesion concern</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{patient.lesion.label} on the {patient.lesion.location.toLowerCase()}.</p>
          <StatusBadge tone="warning" className="mt-4 capitalize"><ShieldAlert className="size-3" /> {lesionStatus}</StatusBadge>
        </div>
        <figure>
          <div className="relative aspect-[4/3] overflow-hidden rounded-lg border bg-muted">
            <Image
              src={patient.lesion.overviewImage.url}
              alt={`Synthetic overview photograph of ${patient.lesion.location}`}
              fill
              className="object-cover"
              sizes="180px"
              priority
            />
          </div>
          <figcaption className="mt-2 text-[11px] text-muted-foreground">First observed {formatInTimeZone(patient.lesion.firstObserved, timezone, { month: "short", day: "numeric", year: "numeric" })}</figcaption>
        </figure>
      </section>

      <section className="border-t pt-7">
        <h2 className="text-sm font-semibold">Risk context</h2>
        <dl className="mt-5 grid gap-y-4 text-xs sm:grid-cols-[130px_1fr] sm:gap-x-6">
          <dt className="text-muted-foreground">Allergies</dt><dd className="font-medium">{patient.allergies.join(", ") || "No active allergies recorded"}</dd>
          <dt className="text-muted-foreground">Family history</dt><dd>{patient.problems.find((problem) => problem.toLowerCase().includes("family history")) ?? "Family history reviewed"}</dd>
          <dt className="text-muted-foreground">Prior atypical nevus</dt><dd>{patient.problems.find((problem) => problem.toLowerCase().includes("atypical")) ?? "No prior atypical nevus recorded"}</dd>
          <dt className="text-muted-foreground">Coverage</dt><dd>{patient.insurance}</dd>
          <dt className="text-muted-foreground">Medications</dt><dd className="space-y-1">{patient.medications.length ? patient.medications.map((medication) => <span key={medication} className="block">{medication}</span>) : "No active medications recorded"}</dd>
        </dl>
      </section>
    </div>
  );
}

function ActiveVisit({ appointment, encounter, pathology, patient, timezone }: { appointment?: Appointment; encounter: Encounter; pathology: Pathology; patient: Patient; timezone: string }) {
  return (
    <section className="order-1 flex min-w-0 flex-col bg-background xl:col-start-2 xl:row-start-1 xl:min-h-[calc(100vh-4.5rem)]" aria-labelledby="active-patient-name">
      <header className="px-5 pb-6 pt-7 sm:px-8">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{appointment?.time ?? "Scheduled"} · {appointment?.visit ?? "Clinical visit"}</p>
            <h1 id="active-patient-name" className="mt-2 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">{patient.name}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{patient.age} years · {patient.pronouns} · DOB {formatInTimeZone(patient.dob, timezone, { month: "short", day: "numeric", year: "numeric" })} · MRN {patient.mrn}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button asChild variant="outline" size="sm"><Link href="/patients/sarah-mitchell"><FileText className="size-4" /> Open chart</Link></Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button variant="outline" size="icon-sm" aria-label="More patient actions"><EllipsisVertical /></Button></DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuLabel>Patient actions</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild><Link href="/messages"><MessageSquareText className="size-4" /> Open messages</Link></DropdownMenuItem>
                <DropdownMenuItem asChild><Link href="/pathology"><Beaker className="size-4" /> View pathology</Link></DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="mt-8 grid gap-5 border-y py-5 sm:grid-cols-[0.8fr_1fr_1fr]">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 size-5 text-emerald-600" />
            <div><p className="text-sm font-semibold">{patient.readiness}% ready</p><p className="mt-1 text-[11px] text-muted-foreground">All intake complete</p></div>
          </div>
          <div className="border-border sm:border-l sm:pl-5"><p className="text-[11px] text-muted-foreground">Coverage</p><p className="mt-1 text-xs font-medium leading-5">{patient.insurance}</p></div>
          <div className="border-border sm:border-l sm:pl-5"><p className="text-[11px] text-muted-foreground">Pharmacy</p><p className="mt-1 text-xs font-medium leading-5">{patient.pharmacy}</p></div>
        </div>
      </header>

      <Tabs defaultValue="overview" className="flex-1 gap-0 px-5 sm:px-8">
        <TabsList variant="line" className="h-10 w-full justify-start gap-7 overflow-x-auto border-b p-0 sm:gap-10">
          <TabsTrigger value="overview" className="h-10 flex-none px-0 text-xs after:bg-primary">Visit overview</TabsTrigger>
          <TabsTrigger value="timeline" className="h-10 flex-none px-0 text-xs after:bg-primary">Timeline</TabsTrigger>
          <TabsTrigger value="history" className="h-10 flex-none px-0 text-xs after:bg-primary">History</TabsTrigger>
          <TabsTrigger value="notes" className="h-10 flex-none px-0 text-xs after:bg-primary">Notes & results</TabsTrigger>
        </TabsList>
        <TabsContent value="overview"><OverviewTab patient={patient} timezone={timezone} /></TabsContent>
        <TabsContent value="timeline" className="py-8">
          <h2 className="text-sm font-semibold">Lesion timeline</h2>
          <div className="mt-5 divide-y border-y">
            {encounter.timeline.length ? encounter.timeline.map((item, index) => <div key={`${item.date}-${item.title}-${index}`} className="grid gap-2 py-4 text-xs sm:grid-cols-[110px_1fr]">
              <p className="font-mono text-muted-foreground">{formatInTimeZone(item.date, timezone, { month: "short", day: "numeric", year: "numeric" })}</p>
              <div><p className="font-semibold">{item.title}</p><p className="mt-1 leading-5 text-muted-foreground">{item.detail}</p></div>
            </div>) : <p className="py-8 text-sm text-muted-foreground">No structured timeline events are available yet.</p>}
          </div>
        </TabsContent>
        <TabsContent value="history" className="py-8">
          <h2 className="text-sm font-semibold">Clinical history</h2>
          <div className="mt-5 grid gap-6 sm:grid-cols-2">
            <section className="border-t pt-4"><h3 className="flex items-center gap-2 text-xs font-semibold"><ShieldAlert className="size-4 text-amber-600" /> Allergies</h3><p className="mt-3 text-xs leading-5 text-muted-foreground">{patient.allergies.join(", ") || "No active allergies recorded"}</p></section>
            <section className="border-t pt-4"><h3 className="flex items-center gap-2 text-xs font-semibold"><Pill className="size-4 text-primary" /> Medications</h3><div className="mt-3 space-y-2 text-xs leading-5 text-muted-foreground">{patient.medications.map((item) => <p key={item}>{item}</p>)}</div></section>
            <section className="border-t pt-4 sm:col-span-2"><h3 className="text-xs font-semibold">Problem list</h3><div className="mt-3 space-y-2 text-xs leading-5 text-muted-foreground">{patient.problems.map((item) => <p key={item}>{item}</p>)}</div></section>
          </div>
        </TabsContent>
        <TabsContent value="notes" className="py-8">
          <h2 className="text-sm font-semibold">Notes and diagnostic results</h2>
          <div className="mt-5 divide-y border-y">
            <div className="flex items-center gap-4 py-4"><ClipboardList className="size-4 text-primary" /><div className="min-w-0 flex-1"><p className="text-xs font-semibold">Changing lesion encounter</p><p className="mt-1 font-mono text-[11px] text-muted-foreground">{encounter.noteId} · v{encounter.note.currentVersion.number}</p></div><StatusBadge tone={encounter.status === "signed" ? "success" : "warning"}>{encounter.status}</StatusBadge></div>
            {pathology ? <div className="flex items-center gap-4 py-4"><Beaker className="size-4 text-primary" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold">{pathology.diagnosis}</p><p className="mt-1 font-mono text-[11px] text-muted-foreground">{pathology.accession}</p></div><StatusBadge tone={pathology.status === "notified" ? "success" : pathology.status === "pending" ? "neutral" : "warning"}>{pathology.status}</StatusBadge></div> : null}
          </div>
        </TabsContent>
      </Tabs>

      <footer className="mt-auto grid gap-3 border-t bg-background px-5 py-4 sm:grid-cols-2 sm:px-8">
        <Button asChild size="lg" data-testid="open-sarah-encounter"><Link href="/encounters/sarah-biopsy"><Stethoscope className="size-4" /> Start visit</Link></Button>
        <Button asChild size="lg" variant="outline"><Link href="/messages"><MessageSquareText className="size-4" /> Message patient</Link></Button>
      </footer>
    </section>
  );
}

function AggregateVisit() {
  return (
    <section className="order-1 flex min-h-[520px] min-w-0 items-center justify-center bg-background px-8 py-14 text-center xl:col-start-2 xl:row-start-1 xl:min-h-[calc(100vh-4.5rem)]">
      <div className="max-w-md">
        <span className="mx-auto flex size-11 items-center justify-center rounded-lg bg-muted text-muted-foreground"><ClipboardList className="size-5" /></span>
        <h1 className="mt-5 text-2xl font-semibold tracking-[-0.035em]">Aggregate command center</h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">Patient-level schedules and clinical records are excluded from the owner session. Open performance intelligence for authorized aggregate reporting.</p>
        <Button asChild className="mt-6"><Link href="/mso">Open performance intelligence <ChevronRight className="size-4" /></Link></Button>
      </div>
    </section>
  );
}

function messageTimestamp(sentAt: string, scenarioTime: string, timezone: string) {
  const messageDay = formatInTimeZone(sentAt, timezone, { year: "numeric", month: "2-digit", day: "2-digit" });
  const scenarioDay = formatInTimeZone(scenarioTime, timezone, { year: "numeric", month: "2-digit", day: "2-digit" });
  return messageDay === scenarioDay
    ? formatInTimeZone(sentAt, timezone, { hour: "numeric", minute: "2-digit" })
    : formatInTimeZone(sentAt, timezone, { month: "short", day: "numeric" });
}

function PriorityRail({ data }: { data: DemoBootstrap }) {
  const pathologyQueue = data.queues.find((queue) => queue.id === "path");
  const messageQueue = data.queues.find((queue) => queue.id === "messages");
  const pathologyLabel = data.patient?.lesion.id ? `${data.patient.lesion.id.slice(0, 13)} · Biopsy` : `${data.pathology?.accession ?? "Pathology"} · Biopsy`;
  const recentMessages = data.conversations
    .flatMap((conversation) => conversation.messages
      .filter((message) => !message.aiDraft)
      .map((message) => ({ ...message, conversationId: conversation.id, unread: conversation.unread > 0 })))
    .sort((left, right) => Date.parse(right.sentAt) - Date.parse(left.sentAt))
    .slice(0, 3);

  return (
    <aside className="order-3 border-t bg-background px-4 py-6 xl:col-start-3 xl:row-start-1 xl:min-h-[calc(100vh-4.5rem)] xl:border-l xl:border-t-0" aria-label="Priority actions">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Priority actions</p>

      <section className="mt-7">
        <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-semibold">Pathology results</h2><StatusBadge tone={pathologyQueue?.count ? "warning" : "neutral"} className="font-mono">{pathologyQueue?.count ?? 0}</StatusBadge></div>
        {data.pathology ? <div className="mt-3 overflow-hidden rounded-lg border bg-card">
          <Link href="/pathology" className="group flex items-start gap-3 p-3.5 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
            <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-amber-50 text-amber-700"><Beaker className="size-3.5" /></span>
            <span className="min-w-0 flex-1"><span className="block truncate text-xs font-semibold">{pathologyLabel}</span><span className="mt-1 block text-[11px] leading-5 text-muted-foreground">{data.pathology.status === "pending" ? "Result pending" : "Result ready"} · Received {formatInTimeZone(data.pathology.receivedAt, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" })}</span></span>
            <ChevronRight className="mt-1 size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Button asChild variant="ghost" className="h-11 w-full justify-between rounded-none border-t px-3 text-xs font-normal"><Link href="/pathology">View all pathology <ExternalLink className="size-3.5" /></Link></Button>
        </div> : <p className="mt-3 rounded-lg border border-dashed px-3 py-5 text-center text-xs text-muted-foreground">No pathology result is available.</p>}
      </section>

      <section className="mt-9">
        <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-semibold">Messages</h2><StatusBadge tone={messageQueue?.count ? "ai" : "neutral"} className="font-mono">{messageQueue?.count ?? 0}</StatusBadge></div>
        <div className="mt-3 overflow-hidden rounded-lg border bg-card">
          {recentMessages.length ? recentMessages.map((message) => <Link key={`${message.conversationId}-${message.id}`} href="/messages" className="group flex items-start gap-3 border-b p-3.5 last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
            <Avatar className="size-8 shrink-0"><AvatarFallback className="bg-violet-100 text-[10px] font-semibold text-violet-700">{initials(message.sender)}</AvatarFallback></Avatar>
            <span className="min-w-0 flex-1"><span className="flex items-center justify-between gap-2"><span className="truncate text-xs font-semibold">{message.sender}</span><span className="shrink-0 text-[10px] text-muted-foreground">{messageTimestamp(message.sentAt, data.scenario.currentTime, data.organization.timezone)}</span></span><span className="mt-1 line-clamp-2 text-[11px] leading-4 text-muted-foreground">{message.body}</span></span>
            <span className="mt-1 flex items-center gap-1.5">{message.unread ? <span className="size-1.5 rounded-full bg-violet-600"><span className="sr-only">Unread</span></span> : null}<ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" /></span>
          </Link>) : <div className="px-3 py-5 text-center"><MessageSquareText className="mx-auto size-4 text-muted-foreground" /><p className="mt-2 text-xs text-muted-foreground">{messageQueue?.detail ?? "No messages need attention."}</p></div>}
          <Button asChild variant="ghost" className="h-11 w-full justify-between rounded-none border-t px-3 text-xs font-normal"><Link href="/messages">View all messages <ExternalLink className="size-3.5" /></Link></Button>
        </div>
      </section>
    </aside>
  );
}

export function CommandCenter() {
  const { data, mode, error, refetch } = useDemoBootstrap();
  const searchParams = useSearchParams();

  if (mode === "loading") return <PageLoading label="Preparing today’s command center" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  if (!data.commandCenter) return <WorkspaceUnavailable title="The command center is not available for your role" />;

  const query = searchParams.get("q")?.trim().toLowerCase() ?? "";
  const appointments = data.schedule.filter((appointment) => !query || [appointment.patient, appointment.visit, appointment.provider].some((value) => value.toLowerCase().includes(query)));
  const featuredAppointment = data.patient ? data.schedule.find((appointment) => appointment.patient === data.patient?.name) : undefined;
  const ownerAggregate = data.session.persona === "owner";

  return (
    <div className="grid min-h-[calc(100vh-4.5rem)] xl:grid-cols-[244px_minmax(0,1fr)_300px]">
      <ScheduleRail
        appointments={appointments}
        featuredPatientName={data.patient?.name}
        ownerAggregate={ownerAggregate}
        query={query}
        scheduledVisits={data.commandCenter.scheduledVisits}
      />
      {data.patient && data.encounter ? <ActiveVisit
        appointment={featuredAppointment}
        encounter={data.encounter}
        pathology={data.pathology}
        patient={data.patient}
        timezone={data.organization.timezone}
      /> : <AggregateVisit />}
      <PriorityRail data={data} />
    </div>
  );
}

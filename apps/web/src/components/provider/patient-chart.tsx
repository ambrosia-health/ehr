"use client";

import {
  Activity,
  ArrowRight,
  Camera,
  Clock3,
  FileClock,
  History,
  MessageSquareText,
  Pill,
  ShieldAlert,
  Sparkles,
  Stethoscope,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { PageHeader, SectionHeader, StatusBadge } from "@/components/product/page-elements";
import { PageError, PageLoading, WorkspaceUnavailable } from "@/components/system/data-state";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { formatInTimeZone } from "@/lib/date";

export function PatientChart() {
  const { data, mode, error, refetch } = useDemoBootstrap();
  if (mode === "loading") return <PageLoading label="Loading Sarah’s chart" />;
  if (!data) return <PageError error={error} retry={refetch} />;
  if (!data.patient || !data.encounter) return <WorkspaceUnavailable title="This patient chart is not available for your role" />;

  const patient = data.patient;
  const lesions = [patient.lesion];
  const encounterComplete = data.encounter.note.status !== "draft";
  const lesionStatus = patient.lesion.status.replaceAll("_", " ");
  const formatChartDate = (value: string) => formatInTimeZone(value, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" });

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Patient chart"
        title={patient.name}
        description={`${patient.age} years · ${patient.pronouns} · DOB ${formatChartDate(patient.dob)} · MRN ${patient.mrn}`}
        actions={<><Button asChild variant="outline"><Link href="/messages"><MessageSquareText className="size-4" /> Message</Link></Button><Button asChild data-testid="start-sarah-visit"><Link href="/encounters/sarah-biopsy"><Stethoscope className="size-4" /> {encounterComplete ? "Open encounter" : "Start visit"}</Link></Button></>}
      />

      <Card className="overflow-hidden">
        <CardContent className="flex flex-col gap-5 p-5 md:flex-row md:items-center">
          <Avatar className="size-14 border-2 border-background shadow-sm"><AvatarFallback className="bg-primary text-base text-primary-foreground">{patient.initials}</AvatarFallback></Avatar>
          <div className="grid flex-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Contact</p><p className="mt-1 text-xs font-medium">{patient.phone}</p><p className="truncate text-[11px] text-muted-foreground">{patient.email}</p></div>
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Coverage</p><p className="mt-1 text-xs font-medium">{patient.insurance}</p></div>
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Pharmacy</p><p className="mt-1 text-xs font-medium">{patient.pharmacy}</p></div>
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Visit readiness</p><p className="mt-1 font-mono text-sm font-semibold">{patient.readiness}%</p><p className="text-[11px] text-muted-foreground">{patient.readinessStatus.replaceAll("_", " ")}</p></div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="summary" className="space-y-5">
        <TabsList className="h-9 w-full justify-start overflow-x-auto bg-transparent p-0">
          <TabsTrigger value="summary">Summary</TabsTrigger><TabsTrigger value="timeline">Timeline</TabsTrigger><TabsTrigger value="lesions">Lesions <span className="ml-1 font-mono text-[10px]">{lesions.length}</span></TabsTrigger><TabsTrigger value="notes">Notes & results</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="mt-0">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(330px,0.7fr)]">
            <div className="space-y-5">
              <Card className="border-violet-200/80 bg-violet-50/35">
                <CardHeader className="pb-3"><SectionHeader title="AI pre-visit brief" description="Generated from the authorized structured intake and chart context" action={<StatusBadge tone="ai"><Sparkles className="size-3" /> Proposal</StatusBadge>} /></CardHeader>
                <CardContent><p className="text-sm leading-6">{data.encounter.previsitSummary}</p>{patient.problems.length ? <div className="mt-4 flex flex-wrap gap-2">{patient.problems.map((problem) => <StatusBadge key={problem} tone="warning">{problem}</StatusBadge>)}</div> : null}<Button asChild size="sm" className="mt-4"><Link href="/encounters/sarah-biopsy">Open encounter <ArrowRight className="size-3.5" /></Link></Button></CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3"><SectionHeader title="Active lesion" description={`${patient.lesion.id} · Longitudinally tracked`} action={<Button asChild variant="outline" size="sm"><Link href="/encounters/sarah-biopsy"><Camera className="size-3.5" /> Compare images</Link></Button>} /></CardHeader>
                <CardContent className="grid gap-5 md:grid-cols-[220px_1fr]">
                  <div className="relative aspect-[4/3] overflow-hidden rounded-lg border bg-muted"><Image src={patient.lesion.overviewImage.url} alt={`Synthetic overview photograph for ${patient.name}: ${patient.lesion.location}`} fill className="object-cover" sizes="220px" priority /></div>
                  <div><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">{patient.lesion.label}</h3><StatusBadge tone={patient.lesion.status === "biopsied" ? "success" : "warning"}>{lesionStatus}</StatusBadge></div><p className="mt-1 text-xs text-muted-foreground">{patient.lesion.location} · First observed {formatChartDate(patient.lesion.firstObserved)}</p><dl className="mt-4 grid gap-x-6 gap-y-3 text-xs sm:grid-cols-2"><div><dt className="text-muted-foreground">Dimensions</dt><dd className="mt-0.5 font-medium">{patient.lesion.dimensions}</dd></div><div><dt className="text-muted-foreground">Morphology</dt><dd className="mt-0.5 font-medium">{patient.lesion.morphology}</dd></div><div><dt className="text-muted-foreground">Border</dt><dd className="mt-0.5 font-medium">{patient.lesion.border}</dd></div><div><dt className="text-muted-foreground">Pigmentation</dt><dd className="mt-0.5 font-medium">{patient.lesion.pigmentation}</dd></div></dl><p className="mt-4 border-t pt-3 text-xs leading-5"><span className="font-semibold">Patient-reported change:</span> {patient.lesion.change}.</p></div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3"><SectionHeader title="Recent lesion observations" description="Structured observation events returned by the clinical read model" /></CardHeader>
                <CardContent className="space-y-0">
                  {data.encounter.timeline.map((event, index, events) => <div key={`${event.date}-${event.title}-${index}`} className="grid grid-cols-[72px_28px_1fr_auto] items-start gap-2"><span className="pt-3 font-mono text-[10px] text-muted-foreground">{formatChartDate(event.date)}</span><div className="relative flex justify-center pt-3"><span className="z-10 flex size-6 items-center justify-center rounded-full border bg-background"><History className="size-3" /></span>{index < events.length - 1 ? <span className="absolute bottom-[-1.5rem] top-9 w-px bg-border" /> : null}</div><div className="py-3"><p className="text-xs font-semibold">{event.title}</p><p className="mt-0.5 text-[11px] text-muted-foreground">{event.detail}</p></div><StatusBadge tone={event.tone} className="mt-3">Recorded</StatusBadge></div>)}
                </CardContent>
              </Card>
            </div>

            <div className="space-y-5">
              <Card><CardHeader className="pb-3"><SectionHeader title="Allergies" action={<StatusBadge tone={patient.allergies.length ? "warning" : "neutral"}>{patient.allergies.length} active</StatusBadge>} /></CardHeader><CardContent>{patient.allergies.length ? patient.allergies.map((allergy) => <div key={allergy} className="flex gap-3 rounded-md bg-amber-50 p-3 text-xs text-amber-950"><ShieldAlert className="size-4 shrink-0 text-amber-700" />{allergy}</div>) : <p className="text-xs text-muted-foreground">No active allergies returned.</p>}</CardContent></Card>
              <Card><CardHeader className="pb-3"><SectionHeader title="Medications" /></CardHeader><CardContent className="space-y-3">{patient.medications.map((medication) => <div key={medication} className="flex gap-3 text-xs"><Pill className="size-4 shrink-0 text-primary" /><p className="font-medium">{medication}</p></div>)}</CardContent></Card>
              <Card><CardHeader className="pb-3"><SectionHeader title="Problem list" /></CardHeader><CardContent className="space-y-3">{patient.problems.map((problem) => <div key={problem} className="flex gap-3 text-xs"><Activity className="size-4 shrink-0 text-primary" /><p>{problem}</p></div>)}</CardContent></Card>
              <Card className="border-sky-200 bg-sky-50/40"><CardHeader className="pb-3"><SectionHeader title="Signed-record integrity" action={<FileClock className="size-4 text-sky-700" />} /></CardHeader><CardContent><p className="text-xs leading-5 text-sky-950/80">Signed notes are immutable. Corrections create a timestamped amendment linked to the original author, note version, provenance, and audit event.</p></CardContent></Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="timeline"><Card><CardContent className="p-6"><SectionHeader title="Lesion observation timeline" description="Structured observations returned for this authorized lesion." /><div className="mt-5 space-y-4">{data.encounter.timeline.map((item, index) => <div key={`${item.date}-${item.title}-${index}`} className="flex gap-4 rounded-lg border p-4"><History className="size-4 text-primary" /><div><p className="text-xs font-semibold">{formatChartDate(item.date)} · {item.title}</p><p className="mt-1 text-xs text-muted-foreground">{item.detail}</p></div></div>)}</div></CardContent></Card></TabsContent>
        <TabsContent value="lesions"><Card><CardContent className="p-6"><SectionHeader title="Lesion registry" description="Authorized lesions returned by the clinical read model." />{lesions.map((lesion) => <div key={lesion.id} className="mt-5 max-w-sm rounded-lg border border-primary/40 bg-primary/5 p-4"><StatusBadge tone={lesion.status === "biopsied" ? "success" : "warning"}>{lesion.status.replaceAll("_", " ")}</StatusBadge><h3 className="mt-3 text-sm font-semibold">{lesion.location}</h3><p className="mt-1 text-xs text-muted-foreground">{lesion.dimensions} · {lesion.change}</p></div>)}</CardContent></Card></TabsContent>
        <TabsContent value="notes"><Card><CardContent className="p-6"><SectionHeader title="Notes and diagnostic results" description="Only records returned for this authorized chart are shown." /><div className="mt-5 divide-y rounded-lg border"><div className="flex items-center gap-4 p-4"><Clock3 className="size-4 text-amber-600" /><div className="flex-1"><p className="text-xs font-semibold">Changing lesion encounter</p><p className="font-mono text-[11px] text-muted-foreground">{data.encounter.noteId} · v{data.encounter.note.currentVersion.number}</p></div><StatusBadge tone={data.encounter.status === "signed" ? "success" : "warning"}>{data.encounter.status}</StatusBadge></div>{data.pathology ? <div className="flex items-center gap-4 p-4"><Activity className="size-4 text-primary" /><div className="flex-1"><p className="text-xs font-semibold">{data.pathology.diagnosis}</p><p className="font-mono text-[11px] text-muted-foreground">{data.pathology.accession}</p></div><StatusBadge tone={data.pathology.status === "notified" ? "success" : data.pathology.status === "pending" ? "neutral" : "warning"}>{data.pathology.status}</StatusBadge></div> : null}</div></CardContent></Card></TabsContent>
      </Tabs>
    </div>
  );
}

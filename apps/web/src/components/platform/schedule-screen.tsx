"use client";

import { CalendarDays, Check, ChevronLeft, ChevronRight, Clock3, MapPin, Sparkles, UsersRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { patientJourneys } from "./platform-fixtures";
import { AgentDock, CareRail, PatientMark, ScreenFrame, ScreenHeader, SectionTitle, StatusPill } from "./platform-ui";

const appointments = [
  { time: "8:30", patient: patientJourneys[0], visit: "New lesion evaluation", room: "Room 2", duration: "30m", readiness: 96, issue: "Biopsy plan review" },
  { time: "9:15", patient: patientJourneys[1], visit: "Acne follow-up", room: "Room 3", duration: "20m", readiness: 100, issue: null },
  { time: "10:00", patient: patientJourneys[3], visit: "Post-Mohs wound check", room: "Room 1", duration: "20m", readiness: 92, issue: "Photo pending" },
  { time: "11:00", patient: patientJourneys[2], visit: "Psoriasis review", room: "Room 4", duration: "30m", readiness: 88, issue: "Labs external" },
  { time: "12:35", patient: patientJourneys[5], visit: "Rash evaluation", room: "Room 2", duration: "25m", readiness: 100, issue: null },
];

export function ScheduleScreen() {
  const [selectedId, setSelectedId] = useState("sarah-mitchell");
  const selected = appointments.find((appointment) => appointment.patient.id === selectedId) ?? appointments[0];

  return <ScreenFrame>
    <ScreenHeader title="The day is already prepared." description="Ambrosia watches readiness, dependencies, room capacity, and care goals—then surfaces only schedule changes that cross policy." action={<div className="flex gap-2"><Button variant="outline" size="icon"><ChevronLeft className="size-4" /></Button><Button variant="outline">Friday, Jul 17</Button><Button variant="outline" size="icon"><ChevronRight className="size-4" /></Button></div>} />
    <div className="mx-auto max-w-[1480px] px-5 py-7 sm:px-8 lg:px-10">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          [CalendarDays, "18", "visits scheduled", "15 fully ready"],
          [Check, "96%", "session readiness", "+8% after overnight work"],
          [UsersRound, "2", "open appointment slots", "waitlist matches ready"],
          [Clock3, "22m", "protected capacity", "from proposed rebalancing"],
        ].map(([Icon, value, label, detail]) => { const I = Icon as typeof CalendarDays; return <div key={String(label)} className="rounded-xl border border-[#d9dfd8] bg-white p-4"><div className="flex items-center gap-2"><I className="size-4 text-[#2b654b]" /><p className="text-xs font-semibold">{label as string}</p></div><p className="mt-4 font-mono text-2xl font-semibold">{value as string}</p><p className="mt-1 text-[10px] text-[#6b7a72]">{detail as string}</p></div>; })}
      </section>

      <div className="mt-7 grid gap-6 xl:grid-cols-[350px_minmax(0,1fr)]">
        <section><SectionTitle title="Today’s session" description="Readiness and dependencies, not appointment color blocks." />
          <div className="mt-4 overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">{appointments.map((appointment) => <button key={appointment.patient.id} type="button" onClick={() => setSelectedId(appointment.patient.id)} className={cn("flex w-full items-start gap-3 border-b border-[#e2e6e1] p-4 text-left last:border-b-0", selectedId === appointment.patient.id ? "bg-[#edf3eb] shadow-[inset_3px_0_0_#2b654b]" : "hover:bg-[#f7f8f4]")}><span className="w-10 shrink-0 font-mono text-xs font-semibold">{appointment.time}</span><PatientMark initials={appointment.patient.initials} size="sm" /><span className="min-w-0 flex-1"><span className="block text-xs font-semibold">{appointment.patient.name}</span><span className="mt-1 block text-[10px] text-[#6b7a72]">{appointment.visit} · {appointment.room} · {appointment.duration}</span><span className="mt-2 flex items-center gap-2"><StatusPill status={appointment.readiness === 100 ? "complete" : appointment.issue?.includes("review") ? "human" : "waiting"}>{appointment.readiness}% ready</StatusPill>{appointment.issue ? <span className="text-[9px] text-[#718078]">{appointment.issue}</span> : null}</span></span></button>)}</div>
        </section>

        <section className="min-w-0"><SectionTitle title={`${selected.patient.name} · ${selected.visit}`} description={`${selected.time} · ${selected.room} · ${selected.duration} · Goal: ${selected.patient.goal}`} action={selected.patient.id === "sarah-mitchell" ? <Button asChild size="sm" className="bg-[#1d563e] text-white hover:bg-[#164630]"><Link href="/patients/sarah-mitchell">Open care agent <ChevronRight className="size-3.5" /></Link></Button> : undefined} />
          <div className="mt-4 overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">
            <div className="flex items-center gap-3 border-b border-[#e1e6e1] p-4"><PatientMark initials={selected.patient.initials} /><div className="flex-1"><p className="text-xs font-semibold">Visit readiness</p><p className="mt-1 text-[10px] text-[#6b7a72]">Insurance, intake, records, room, and follow-up capacity reconciled.</p></div><span className="font-mono text-lg font-semibold">{selected.readiness}%</span></div>
            <div className="overflow-x-auto p-5"><CareRail steps={selected.patient.steps} compact /></div>
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-[#d9dfd8] bg-white p-5"><div className="flex items-center gap-2"><Sparkles className="size-4 text-[#2b654b]" /><h3 className="text-sm font-semibold">Ambrosia recommends</h3></div><p className="mt-3 text-xs leading-5 text-[#5f7067]">Move the 2:40 PM low-complexity follow-up into the open 1:50 PM slot. This protects 22 minutes for a same-day lesion evaluation and stays within approved templates.</p><div className="mt-4 flex gap-2"><Button size="sm" className="bg-[#1d563e] text-white hover:bg-[#164630]">Approve change</Button><Button variant="outline" size="sm">See impact</Button></div></div>
            <div className="rounded-xl border border-[#d9dfd8] bg-white p-5"><div className="flex items-center gap-2"><MapPin className="size-4 text-[#2b654b]" /><h3 className="text-sm font-semibold">Capacity monitor</h3></div><div className="mt-4 space-y-3 text-xs">{[["Rooms", "4 of 5 active"], ["Admin operations", "Automated"], ["Procedure capacity", "1 same-day opening"], ["Waitlist", "3 policy matches"]].map(([label, value]) => <div key={label} className="flex justify-between border-b border-[#e5e8e3] pb-3 last:border-b-0"><span className="text-[#6a7971]">{label}</span><span className="font-semibold">{value}</span></div>)}</div></div>
          </div>
        </section>
      </div>
    </div>
    <AgentDock />
  </ScreenFrame>;
}

"use client";

import { ChevronDown, ChevronRight, Filter, ListFilter, UsersRound } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { patientJourneys, stateTone } from "./platform-fixtures";
import { AgentDock, CareRail, PatientMark, ScreenFrame, ScreenHeader, SearchField, SectionTitle, StatusPill } from "./platform-ui";

const savedViews = ["Active goals", "Unresolved pathology", "Interval change", "Biologic monitoring", "Patient overdue", "Surveillance due", "Recently closed"];

export function PatientsScreen() {
  const [query, setQuery] = useState("");
  const [view, setView] = useState("Active goals");
  const [expanded, setExpanded] = useState<string | null>("sarah-mitchell");
  const filtered = useMemo(() => patientJourneys.filter((patient) => {
    const matchesQuery = [patient.name, patient.mrn, patient.concern, patient.goal, patient.state].join(" ").toLowerCase().includes(query.toLowerCase());
    if (!matchesQuery) return false;
    if (view === "Unresolved pathology") return patient.id === "sarah-mitchell" || patient.id === "jordan-lee";
    if (view === "Interval change") return patient.id === "sarah-mitchell";
    if (view === "Biologic monitoring") return patient.id === "natalie-wong";
    if (view === "Patient overdue") return patient.state === "Waiting patient";
    if (view === "Recently closed") return patient.id === "benjamin-carter";
    return true;
  }), [query, view]);

  return (
    <ScreenFrame>
      <ScreenHeader title="Every patient has a horizon." description="312 durable care journeys, compressed by goal, current state, and the next meaningful step—not by chart activity." action={<Button variant="outline"><UsersRound className="size-4" />312 active patients</Button>} />
      <div className="mx-auto max-w-[1480px] px-5 py-7 sm:px-8 lg:px-10">
        <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)]">
          <aside>
            <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#6c7b73]">Saved views</p>
            <nav className="space-y-1" aria-label="Saved patient views">
              {savedViews.map((item) => <button type="button" key={item} onClick={() => setView(item)} className={cn("flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-xs", view === item ? "bg-[#e5ede4] font-semibold text-[#1e513b]" : "text-[#596b61] hover:bg-[#f0f3ee]")}><span>{item}</span><span className="font-mono text-[9px] text-[#75847c]">{item === "Active goals" ? 312 : item === "Unresolved pathology" ? 37 : item === "Interval change" ? 11 : item === "Biologic monitoring" ? 24 : item === "Patient overdue" ? 12 : item === "Recently closed" ? 46 : 29}</span></button>)}
            </nav>
            <div className="mt-6 rounded-xl border border-[#d9dfd8] bg-white p-4"><div className="flex items-center gap-2"><ListFilter className="size-4 text-[#2b654b]" /><p className="text-xs font-semibold">Portfolio logic</p></div><p className="mt-2 text-[10px] leading-4 text-[#687870]">Administrative work can be managed as a policy-identical cohort. Clinical approvals always remain patient-specific.</p></div>
          </aside>

          <main className="min-w-0">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="w-full max-w-xl"><SearchField value={query} onChange={setQuery} placeholder="Search patient, MRN, lesion, diagnosis, result, or goal" /></div>
              <Button variant="outline"><Filter className="size-4" />Stop reason · Any</Button>
            </div>
            <div className="mt-6"><SectionTitle title={view} description={`${filtered.length} representative journeys shown · 312 total`} /></div>

            <div className="mt-4 overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">
              <div className="hidden grid-cols-[minmax(230px,1fr)_170px_minmax(180px,1fr)_minmax(180px,1fr)_150px_36px] gap-3 border-b border-[#dfe5df] bg-[#f5f7f3] px-4 py-3 text-[9px] font-semibold uppercase tracking-[0.12em] text-[#718078] lg:grid">
                <span>Patient & goal</span><span>Current state</span><span>Last meaningful event</span><span>Next step</span><span>Owner</span><span />
              </div>
              {filtered.length ? filtered.map((patient) => {
                const isExpanded = expanded === patient.id;
                return <div key={patient.id} className="border-b border-[#e2e6e1] last:border-b-0">
                  <div className="grid gap-3 px-4 py-4 lg:grid-cols-[minmax(230px,1fr)_170px_minmax(180px,1fr)_minmax(180px,1fr)_150px_36px] lg:items-center">
                    <div className="flex items-start gap-3"><PatientMark initials={patient.initials} /><div className="min-w-0"><Link href={patient.id === "sarah-mitchell" ? "/patients/sarah-mitchell" : "#"} className="text-xs font-semibold hover:underline">{patient.name}</Link><p className="mt-1 text-[10px] text-[#718078]">{patient.age} y · {patient.pronouns} · {patient.mrn}</p><p className="mt-2 text-[10px] leading-4 text-[#385447]">{patient.goal}</p></div></div>
                    <div><StatusPill status={stateTone[patient.state]}>{patient.state}</StatusPill><p className="mt-1 text-[9px] text-[#7b8881]">{patient.horizon}</p></div>
                    <p className="text-[10px] leading-4 text-[#5f7067]">{patient.lastEvent}</p>
                    <p className="text-xs font-semibold leading-4 text-[#284d3b]">{patient.next}</p>
                    <p className="text-[10px] text-[#5f7067]">{patient.owner}</p>
                    <button type="button" onClick={() => setExpanded(isExpanded ? null : patient.id)} className="flex size-8 items-center justify-center rounded-md hover:bg-[#edf1eb]" aria-label={`${isExpanded ? "Collapse" : "Expand"} ${patient.name} care horizon`}>{isExpanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}</button>
                  </div>
                  {isExpanded ? <div className="border-t border-[#e4e8e3] bg-[#fbfcf9] px-4 py-5"><div className="overflow-x-auto"><CareRail steps={patient.steps} /></div>{patient.id === "sarah-mitchell" ? <div className="mt-4 flex justify-end"><Button asChild size="sm" className="bg-[#1d563e] text-white hover:bg-[#164630]"><Link href="/patients/sarah-mitchell">Open Sarah’s care agent <ChevronRight className="size-3.5" /></Link></Button></div> : null}</div> : null}
                </div>;
              }) : <div className="px-6 py-16 text-center"><p className="text-sm font-semibold">No journeys match this view.</p><p className="mt-2 text-xs text-[#6b7a72]">Try another saved view or clear your search.</p></div>}
            </div>
          </main>
        </div>
      </div>
      <AgentDock />
    </ScreenFrame>
  );
}

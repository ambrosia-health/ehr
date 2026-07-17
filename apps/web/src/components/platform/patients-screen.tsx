"use client";

import { ArrowRight, CheckCircle2, Search, UsersRound } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import { patientJourneys, type PatientJourney } from "./platform-fixtures";
import { ScreenFrame } from "./platform-ui";

type StatusFilter = "All" | "Needs clinician" | "Advancing" | "Waiting";

const statusFilters: StatusFilter[] = ["All", "Needs clinician", "Advancing", "Waiting"];

function matchesStatus(state: PatientJourney["state"], filter: StatusFilter) {
  if (filter === "All") return true;
  if (filter === "Waiting") return state.startsWith("Waiting");
  return state === filter;
}

function statusClassName(state: PatientJourney["state"]) {
  if (state === "Needs clinician") return "border-[#f2ce8f] bg-[#fff9ed] text-[#9a4d08]";
  if (state === "Advancing") return "border-[#9ed8cf] bg-[#effaf7] text-[#0f6d65]";
  if (state === "At risk") return "border-[#fecaca] bg-[#fff1f2] text-[#b42318]";
  return "border-[#b8d2f4] bg-[#f2f7ff] text-[#245c9d]";
}

function PatientIdentity({ patient }: { patient: PatientJourney }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-md border border-[#cbd9eb] bg-[#eff5ff] text-[10px] font-semibold text-[#174f91]">
        {patient.initials}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-[13px] font-semibold text-[#172033]">{patient.name}</span>
        <span className="mt-0.5 block truncate text-[10px] text-[#697386]">
          {patient.age} y · {patient.pronouns} · {patient.mrn}
        </span>
      </span>
    </div>
  );
}

function PatientRowContent({ patient }: { patient: PatientJourney }) {
  return (
    <>
      <PatientIdentity patient={patient} />
      <div className="min-w-0">
        <p className="truncate text-xs font-medium text-[#273247]">{patient.concern}</p>
        <p className="mt-1 truncate text-[10px] text-[#6c7688]">{patient.goal}</p>
      </div>
      <div>
        <span className={cn("inline-flex rounded-md border px-2 py-1 text-[10px] font-semibold", statusClassName(patient.state))}>
          {patient.state}
        </span>
      </div>
      <p className="text-[10px] leading-4 text-[#606b7d]">{patient.lastEvent}</p>
      <div className="flex min-w-0 items-center justify-between gap-3">
        <p className="text-xs font-medium leading-4 text-[#202a3b]">{patient.next}</p>
        {patient.id === "sarah-mitchell" ? <ArrowRight className="size-4 shrink-0 text-[#0b5fc6]" aria-hidden="true" /> : null}
      </div>
    </>
  );
}

export function PatientsScreen() {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("All");
  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return patientJourneys.filter((patient) => {
      const matchesQuery = !normalizedQuery || [patient.name, patient.mrn, patient.concern, patient.goal, patient.state, patient.next]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);

      return matchesQuery && matchesStatus(patient.state, statusFilter);
    });
  }, [query, statusFilter]);

  return (
    <ScreenFrame className="bg-[#f8fafc] text-[#172033]">
      <main className="mx-auto max-w-[1240px] px-4 py-6 sm:px-7 lg:px-10 lg:py-8">
        <header className="flex flex-col gap-4 border-b border-[#d8dee8] pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#0b5fc6]">Clinical worklist</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-[-0.035em] text-[#101828]">Patients</h1>
            <p className="mt-1.5 text-xs leading-5 text-[#667085]">Current state and next action across every active care journey.</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-[#475467]">
            <UsersRound className="size-4 text-[#0b5fc6]" aria-hidden="true" />
            <span className="font-semibold text-[#1d2939]">312</span> active journeys
          </div>
        </header>

        <section className="mt-5 overflow-hidden rounded-lg border border-[#d8dee8] bg-white" aria-labelledby="patient-worklist-title">
          <div className="flex flex-col gap-4 border-b border-[#d8dee8] px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-baseline gap-3">
              <h2 id="patient-worklist-title" className="text-sm font-semibold text-[#1d2939]">Patient worklist</h2>
              <p className="text-[10px] text-[#7b8495]">{filtered.length} of {patientJourneys.length} shown</p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter patients by status">
                {statusFilters.map((filter) => (
                  <button
                    key={filter}
                    type="button"
                    aria-pressed={statusFilter === filter}
                    onClick={() => setStatusFilter(filter)}
                    className={cn(
                      "h-8 rounded-md border px-3 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0b5fc6]/35",
                      statusFilter === filter
                        ? "border-[#0b5fc6] bg-[#eef5ff] text-[#084f9f]"
                        : "border-[#d7dee8] bg-white text-[#596477] hover:border-[#9eb8da] hover:text-[#174f91]",
                    )}
                  >
                    {filter}
                  </button>
                ))}
              </div>
              <div className="relative w-full sm:w-[300px]">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#7b8495]" aria-hidden="true" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search name, MRN, or concern"
                  aria-label="Search patients"
                  className="h-9 rounded-md border-[#cfd7e3] bg-white pl-9 text-xs shadow-none focus-visible:border-[#0b5fc6] focus-visible:ring-[#0b5fc6]/20"
                />
              </div>
            </div>
          </div>

          <div className="hidden grid-cols-[1.15fr_1fr_150px_1fr_1fr] gap-4 border-b border-[#d8dee8] bg-[#f8fafc] px-4 py-2.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-[#667085] md:grid" aria-hidden="true">
            <span>Patient</span>
            <span>Concern</span>
            <span>Status</span>
            <span>Last activity</span>
            <span>Next action</span>
          </div>

          <div className="divide-y divide-[#e1e6ee]">
            {filtered.map((patient) => {
              const className = "grid gap-3 px-4 py-3.5 transition-colors md:grid-cols-[1.15fr_1fr_150px_1fr_1fr] md:items-center md:gap-4";

              return patient.id === "sarah-mitchell" ? (
                <Link
                  key={patient.id}
                  href="/patients/sarah-mitchell"
                  aria-label={`Open ${patient.name}`}
                  className={cn(className, "hover:bg-[#f5f9ff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0b5fc6]")}
                >
                  <PatientRowContent patient={patient} />
                </Link>
              ) : (
                <article key={patient.id} className={className}>
                  <PatientRowContent patient={patient} />
                </article>
              );
            })}
          </div>

          {filtered.length === 0 ? (
            <div className="border-t border-[#e1e6ee] px-4 py-12 text-center">
              <CheckCircle2 className="mx-auto size-6 text-[#0b5fc6]" aria-hidden="true" />
              <p className="mt-3 text-sm font-semibold text-[#273247]">No patient matches this view.</p>
              <p className="mt-1 text-xs text-[#697386]">Adjust the status filter or try another search.</p>
            </div>
          ) : null}
        </section>
      </main>
    </ScreenFrame>
  );
}

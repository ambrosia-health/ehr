"use client";

import {
  ArrowUpRight,
  Beaker,
  CalendarCheck2,
  Check,
  FileCheck2,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  Stethoscope,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

import { attentionItems, patientJourneys, type AttentionItem } from "./platform-fixtures";
import {
  AgentDock,
  ApprovalReceipt,
  CareRail,
  HorizonTabs,
  PatientMark,
  PortfolioStat,
  PrimaryArrow,
  ScreenFrame,
  ScreenHeader,
  SectionTitle,
  StatusPill,
  SystemStatus,
} from "./platform-ui";

const silentEvents = [
  { time: "8:14", icon: FileCheck2, title: "Previsit synthesis completed", detail: "Emily Lopez · 14 sources reconciled", confidence: "94%" },
  { time: "8:12", icon: Beaker, title: "Pathology monitor advanced", detail: "Jordan Lee · result matched to specimen", confidence: "98%" },
  { time: "8:10", icon: MessageSquareText, title: "Aftercare delivered", detail: "Alex Rivera · portal read receipt received", confidence: "Policy" },
  { time: "8:07", icon: ShieldCheck, title: "Coverage verified", detail: "Sarah Mitchell · Blue Horizon PPO", confidence: "99%" },
];

export function TodayScreen() {
  const [horizon, setHorizon] = useState("Now");
  const [selected, setSelected] = useState<AttentionItem | null>(null);
  const [resolved, setResolved] = useState<Set<string>>(() => new Set());
  const openItems = useMemo(() => attentionItems.filter((item) => !resolved.has(item.id)), [resolved]);
  const journeys = horizon === "Now" ? patientJourneys.slice(0, 4) : horizon === "24 hours" ? patientJourneys.slice(1, 5) : patientJourneys.slice(2);

  function approve(item: AttentionItem) {
    setResolved((current) => new Set(current).add(item.id));
  }

  return (
    <ScreenFrame>
      <ScreenHeader
        eyebrow="Dermatologist workspace"
        title="You practice medicine. Ambrosia runs the clinic."
        description={`Overnight, Ambrosia handled intake, scheduling, follow-up, and billing across 312 patients. ${openItems.length || "No"} clinical ${openItems.length === 1 ? "decision needs" : "decisions need"} you; there is no administrative queue to manage.`}
        action={<div className="flex flex-wrap items-center gap-4"><SystemStatus detail={`${309 + resolved.size} journeys are advancing`} />{openItems.length ? <PrimaryArrow onClick={() => setSelected(openItems[0] ?? null)}>Resolve {openItems.length} stops</PrimaryArrow> : null}</div>}
      />

      <section className="border-b border-[#dce3db] px-5 py-5 sm:px-8 lg:px-10" aria-label="Clinic portfolio summary">
        <div className="mx-auto grid max-w-[1480px] grid-cols-2 gap-y-5 md:grid-cols-5">
          <PortfolioStat value="312" label="active care journeys" status="moving" />
          <PortfolioStat value={`${278 + resolved.size}`} label="advancing safely" status="complete" />
          <PortfolioStat value="19" label="waiting on external systems" status="waiting" />
          <PortfolioStat value="12" label="waiting on patients" status="waiting" />
          <PortfolioStat value={String(openItems.length)} label="need clinician judgment" status="human" active={openItems.length > 0} />
        </div>
      </section>

      <HorizonTabs value={horizon} onChange={setHorizon} />

      <div className="mx-auto max-w-[1480px] px-5 py-7 sm:px-8 lg:px-10">
        <section id="decisions">
          <SectionTitle title={`Needs your judgment · ${openItems.length}`} description="Ambrosia stops only where clinical judgment, attestation, or conflicting evidence requires a person." action={<span className="text-[10px] text-[#74827a]">Ordered by clinical risk and deadline</span>} />
          {openItems.length ? <div className="mt-4 grid gap-3 xl:grid-cols-3">
            {openItems.map((item) => (
              <article key={item.id} className="group flex min-h-[260px] flex-col rounded-xl border border-[#d9dfd8] bg-white p-5 shadow-[0_10px_35px_rgba(20,61,45,0.035)] transition-all hover:-translate-y-0.5 hover:border-[#c9d3ca] hover:shadow-[0_14px_40px_rgba(20,61,45,0.07)]">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3"><PatientMark initials={item.initials} /><div><p className="text-sm font-semibold">{item.patient}</p><p className="text-[10px] text-[#6c7a72]">{item.episode} · {item.domain}</p></div></div>
                  <StatusPill status={item.severity}>{item.due}</StatusPill>
                </div>
                <div className="mt-5 border-l-2 border-[#d17a11] pl-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#a45a05]">Why Ambrosia stopped</p>
                  <p className="mt-2 text-xs leading-5 text-[#4b5d54]">{item.reason}</p>
                </div>
                <div className="mt-4"><p className="text-[10px] text-[#718078]">Recommended next step</p><p className="mt-1 text-sm font-semibold leading-5">{item.recommendation}</p></div>
                <div className="mt-auto flex items-end justify-between gap-3 pt-5">
                  <p className="text-[10px] leading-4 text-[#6d7c74]">{item.confidence}% confidence<br />{item.release.split(",").length} downstream actions staged</p>
                  <Button size="sm" onClick={() => setSelected(item)} className="bg-[#c76c00] text-white hover:bg-[#a95c00]">Review <ArrowUpRight className="size-3.5" /></Button>
                </div>
              </article>
            ))}
          </div> : <div className="mt-4"><ApprovalReceipt><p className="font-semibold">All clinical stops are resolved.</p><p className="mt-1 text-xs text-[#557064]">Ambrosia released the approved downstream actions and continues monitoring every journey.</p></ApprovalReceipt></div>}
        </section>

        <div className="mt-9 grid gap-7 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]">
          <section className="min-w-0">
            <SectionTitle title={`${horizon} care horizons`} description={`${journeys.length} representative journeys; the full portfolio remains searchable in Patients.`} action={<Button asChild variant="outline" size="sm"><Link href="/patients">View all 312 patients</Link></Button>} />
            <div className="mt-4 overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">
              {journeys.map((journey) => (
                <div key={journey.id} className="grid border-b border-[#e1e6df] last:border-b-0 lg:grid-cols-[190px_minmax(0,1fr)]">
                  <Link href={journey.id === "sarah-mitchell" ? "/patients/sarah-mitchell" : "/patients"} className="flex items-start gap-3 border-b border-[#e1e6df] p-4 hover:bg-[#f6f8f3] lg:border-b-0 lg:border-r">
                    <PatientMark initials={journey.initials} />
                    <span className="min-w-0"><span className="block text-xs font-semibold">{journey.name}</span><span className="mt-1 block text-[10px] text-[#6c7a72]">{journey.concern}</span><span className="mt-2 block text-[10px] leading-4 text-[#3d594b]">{journey.goal}</span></span>
                  </Link>
                  <div className="overflow-x-auto p-4"><CareRail steps={journey.steps} compact /></div>
                </div>
              ))}
            </div>
          </section>

          <aside>
            <SectionTitle title="The work you didn’t have to staff" description="Recent autonomous work across clinical, communication, and revenue systems." />
            <div className="mt-4 overflow-hidden rounded-xl border border-[#d9dfd8] bg-white">
              {silentEvents.map((event) => { const Icon = event.icon; return <div key={`${event.time}-${event.title}`} className="flex gap-3 border-b border-[#e5e8e3] p-4 last:border-b-0"><span className="font-mono text-[10px] text-[#728078]">{event.time}</span><Icon className="size-4 shrink-0 text-[#2b654b]" /><div className="min-w-0 flex-1"><p className="text-xs font-semibold">{event.title}</p><p className="mt-1 text-[10px] leading-4 text-[#6a7971]">{event.detail}</p></div><span className="text-[9px] text-[#738178]">{event.confidence}</span></div>; })}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-[#d9dfd8] bg-white p-4"><div className="flex items-center gap-2"><CalendarCheck2 className="size-4 text-[#2b654b]" /><p className="text-xs font-semibold">Today’s session</p></div><p className="mt-3 font-mono text-2xl font-semibold">18</p><p className="mt-1 text-[10px] text-[#6d7c74]">15 ready · 2 intake · 1 coverage</p></div>
              <div className="rounded-xl border border-[#d9dfd8] bg-white p-4"><div className="flex items-center gap-2"><ShieldCheck className="size-4 text-[#2b654b]" /><p className="text-xs font-semibold">Admin coverage</p></div><p className="mt-3 font-mono text-2xl font-semibold">100%</p><p className="mt-1 text-[10px] text-[#6d7c74]">intake to payment, operated by Ambrosia</p></div>
            </div>
          </aside>
        </div>
      </div>

      <Sheet open={Boolean(selected)} onOpenChange={(open) => { if (!open) setSelected(null); }}>
        <SheetContent className="w-full overflow-y-auto border-l border-[#d9dfd8] bg-[#fffefa] p-0 sm:max-w-[520px]">
          {selected ? <>
            <SheetHeader className="border-b border-[#dce3db] p-6 text-left">
              <div className="flex items-center gap-3"><PatientMark initials={selected.initials} size="lg" /><div><SheetTitle className="text-xl tracking-[-0.03em]">{selected.patient}</SheetTitle><SheetDescription>{selected.episode} · {selected.domain} decision</SheetDescription></div></div>
            </SheetHeader>
            <div className="space-y-6 p-6">
              {resolved.has(selected.id) ? <ApprovalReceipt><p className="font-semibold">Decision approved and released.</p><p className="mt-1 text-xs">{selected.release} are now advancing.</p></ApprovalReceipt> : null}
              <section><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#a65b06]">Why Ambrosia stopped</p><p className="mt-2 text-sm leading-6 text-[#45574e]">{selected.reason}</p></section>
              <section className="rounded-xl border border-[#d8dfd8] bg-white p-4"><div className="flex items-center gap-2"><Sparkles className="size-4 text-[#286047]" /><h3 className="text-sm font-semibold">Recommended plan</h3></div><p className="mt-3 text-sm leading-6">{selected.recommendation}</p><div className="mt-4 flex items-center justify-between border-t border-[#e2e7e1] pt-3 text-[10px] text-[#697971]"><span>{selected.confidence}% confidence</span><button type="button" className="font-semibold text-[#245942]">View evidence & rationale</button></div></section>
              <section><h3 className="text-sm font-semibold">Approval releases</h3><div className="mt-3 space-y-2">{selected.release.split(", ").map((action) => <div key={action} className="flex items-center gap-3 text-xs"><span className="flex size-5 items-center justify-center rounded-full border border-[#91ae9b] bg-[#f2f7f2]"><Check className="size-3 text-[#275e43]" /></span>{action}</div>)}</div></section>
              <section className="rounded-lg border border-[#d9dfd8] bg-[#f5f7f2] p-4"><div className="flex items-center gap-2"><ShieldCheck className="size-4 text-[#285e45]" /><p className="text-xs font-semibold">Permission boundary</p></div><p className="mt-2 text-[11px] leading-5 text-[#63736a]">Ambrosia may prepare and coordinate. It cannot diagnose, prescribe, sign, or notify this patient of a clinical result without an authorized clinician.</p></section>
              <div className="flex gap-2"><Button variant="outline" className="flex-1">Edit plan</Button><Button disabled={resolved.has(selected.id)} onClick={() => approve(selected)} className="flex-1 bg-[#c76c00] text-white hover:bg-[#a95c00]"><Stethoscope className="size-4" />{resolved.has(selected.id) ? "Approved" : "Approve & release"}</Button></div>
            </div>
          </> : null}
        </SheetContent>
      </Sheet>

      <AgentDock />
    </ScreenFrame>
  );
}

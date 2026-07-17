"use client";

import {
  ArrowRight,
  Beaker,
  CalendarDays,
  Check,
  ClipboardCheck,
  ClipboardList,
  Clock3,
  FileText,
  MessageSquareText,
  ShieldCheck,
  TrendingUp,
  UsersRound,
} from "lucide-react";
import Image from "next/image";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

import { ScreenFrame } from "./platform-ui";

const defaultRecommendation = "Single-site procedure under local anesthesia. Send specimen to Hudson Community Lab and monitor through diagnostic closure.";

export function PatientAgentScreen() {
  const [approved, setApproved] = useState(false);
  const [modifyOpen, setModifyOpen] = useState(false);
  const [recommendation, setRecommendation] = useState(defaultRecommendation);
  const [draftRecommendation, setDraftRecommendation] = useState(defaultRecommendation);

  function changeModifyOpen(open: boolean) {
    if (open) setDraftRecommendation(recommendation);
    setModifyOpen(open);
  }

  function saveRecommendation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextRecommendation = draftRecommendation.trim();
    if (!nextRecommendation) return;

    setRecommendation(nextRecommendation);
    setModifyOpen(false);
  }

  return (
    <ScreenFrame className="bg-[#f7f8f7] px-3 py-5 sm:px-6 sm:py-8">
      <main className="mx-auto max-w-[1080px] overflow-hidden rounded-lg border border-[#d9dfe5] bg-white text-[#172033]">
        <header className="flex min-h-24 flex-col gap-4 border-b border-[#dde2e8] px-5 py-4 sm:px-6 md:flex-row md:items-center md:justify-between">
          <div className="flex min-w-0 items-center gap-4">
            <Image
              src="/images/patients/sarah-mitchell.png"
              alt="Sarah Mitchell"
              width={64}
              height={64}
              className="size-16 shrink-0 rounded-full border border-[#d9dfe5] object-cover"
            />
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-semibold tracking-[-0.035em] text-[#111827]">Sarah Mitchell</h1>
              <p className="mt-1 text-sm text-[#667085]">38 y · she/her · MRN AM-10482</p>
            </div>
          </div>
          <div className="flex items-start gap-3 text-sm text-[#344054] md:max-w-[280px]">
            <CalendarDays className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <p>
              <span className="font-medium">Visit planned: Jul 20, 2026 at 8:30 AM</span>
              <span className="mt-0.5 block text-xs text-[#7b8495]">Biopsy slot held</span>
            </p>
          </div>
        </header>

        <section aria-labelledby="decision-title" className="px-5 pb-4 pt-5 sm:px-6">
          <div className="grid items-stretch gap-5 lg:grid-cols-[minmax(290px,1.05fr)_minmax(350px,1fr)_190px]">
            <div className="py-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#0f5cc4]">Decision 1 of 3</p>
              <h2 id="decision-title" className="mt-3 text-[clamp(1.75rem,2.45vw,2rem)] font-semibold leading-[1.08] tracking-[-0.045em] text-[#111827]">
                Biopsy this changing lesion?
              </h2>
              <p className="mt-4 text-sm text-[#667085]">Left posterior shoulder&nbsp;&nbsp;·&nbsp;&nbsp;Observed Jul 16</p>
            </div>

            <section aria-labelledby="recommended-plan-title" className="grid min-h-[136px] rounded-md bg-[#f7f7f5] p-4 sm:grid-cols-[minmax(0,1fr)_110px]">
              <div className="sm:pr-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#0f5cc4]">Recommended plan</p>
                <h3 id="recommended-plan-title" className="mt-3 text-xl font-semibold tracking-[-0.025em] text-[#111827]">Shave biopsy</h3>
                <p className="mt-1.5 text-[11px] leading-[18px] text-[#475467]">{recommendation}</p>
              </div>
              <div className="mt-4 flex items-center gap-3 border-t border-[#dfe3e7] pt-4 sm:mt-7 sm:block sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0 sm:text-center">
                <div className="flex items-center justify-center gap-2 text-[#167a83]">
                  <ShieldCheck className="size-6 shrink-0" strokeWidth={2} aria-hidden="true" />
                  <span className="text-2xl font-semibold tracking-[-0.04em]">91%</span>
                </div>
                <p className="mt-1 text-xs text-[#667085]">confidence</p>
              </div>
            </section>

            <div className="flex flex-col justify-between gap-3">
              <div aria-live="polite" className={approved ? "text-[#167a83]" : "text-[#b85e00]"}>
                <div className="flex items-start gap-2">
                  {approved ? <Check className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> : <Clock3 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />}
                  <p className="whitespace-nowrap text-[11px] font-semibold">{approved ? "Released just now" : "Deadline: Before Jul 20, 2026"}</p>
                </div>
                <p className="ml-6 mt-1 text-xs text-[#667085]">{approved ? "Six actions advancing" : "About 2 minutes"}</p>
              </div>
              <div className="grid gap-2.5">
                <Button
                  type="button"
                  size="lg"
                  disabled={approved}
                  onClick={() => setApproved(true)}
                  className="h-11 rounded-md bg-[#0f5cc4] text-sm font-medium text-white shadow-[0_3px_8px_rgba(15,92,196,0.18)] hover:bg-[#0b4ea9]"
                >
                  {approved ? <Check className="size-4" /> : null}
                  {approved ? "Approved & released" : "Approve & release"}
                </Button>
                <Button
                  type="button"
                  size="lg"
                  variant="outline"
                  disabled={approved}
                  aria-expanded={modifyOpen}
                  aria-controls="modify-biopsy-plan"
                  onClick={() => changeModifyOpen(true)}
                  className="h-11 rounded-md border-[#9ca6b5] bg-white text-sm font-medium text-[#172033] shadow-none hover:bg-[#f5f7fa]"
                >
                  Modify
                </Button>
              </div>
            </div>
          </div>

          <div className="mt-4 grid gap-2.5 md:grid-cols-2">
            <figure className="overflow-hidden rounded-md border border-[#d9dfe5] bg-[#fafafa]">
              <figcaption className="flex h-9 items-center justify-between gap-3 border-b border-[#d9dfe5] px-3 text-xs text-[#667085]">
                <span className="font-medium text-[#344054]">Clinical photo</span>
                <span>Jul 16&nbsp;&nbsp;·&nbsp;&nbsp;7 × 5 mm</span>
              </figcaption>
              <Image
                src="/images/clinical/sarah-left-posterior-shoulder.png"
                alt="Clinical photograph of Sarah Mitchell's left posterior shoulder lesion with a measurement scale"
                width={1120}
                height={510}
                priority
                sizes="(min-width: 1280px) 540px, (min-width: 768px) 45vw, 100vw"
                className="aspect-[2.3/1] w-full object-cover object-[center_72%]"
              />
            </figure>
            <figure className="overflow-hidden rounded-md border border-[#d9dfe5] bg-[#fafafa]">
              <figcaption className="flex h-9 items-center justify-between gap-3 border-b border-[#d9dfe5] px-3 text-xs text-[#667085]">
                <span className="font-medium text-[#344054]">Dermoscopy</span>
                <span>Jul 16&nbsp;&nbsp;·&nbsp;&nbsp;polarized</span>
              </figcaption>
              <Image
                src="/images/clinical/sarah-left-posterior-shoulder-dermoscopy.png"
                alt="Dermoscopy image of Sarah Mitchell's left posterior shoulder lesion showing irregular pigmentation"
                width={1120}
                height={510}
                priority
                sizes="(min-width: 1280px) 540px, (min-width: 768px) 45vw, 100vw"
                className="aspect-[2.3/1] w-full scale-[1.6] bg-black object-contain"
              />
            </figure>
          </div>

          <section aria-labelledby="key-evidence-title" className="mt-4">
            <h3 id="key-evidence-title" className="mb-2 text-base font-semibold tracking-[-0.02em] text-[#172033]">Key evidence</h3>
            <div className="overflow-x-auto rounded-md border border-[#d9dfe5]">
              <table className="w-full min-w-[800px] table-fixed border-collapse text-left text-xs leading-4 text-[#475467]">
                <colgroup>
                  <col className="w-[130px]" />
                  <col />
                  <col className="w-[145px]" />
                  <col className="w-[290px]" />
                </colgroup>
                <tbody>
                  <tr>
                    <th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-medium text-[#475467]"><span className="flex items-center gap-3"><TrendingUp className="size-4 shrink-0" aria-hidden="true" />What changed</span></th>
                    <td className="border-b border-r border-[#e0e4e9] p-3 align-top"><span className="block">Widened to <strong className="font-semibold text-[#243044]">7 × 5 mm</strong> over approximately four months.</span><span className="block">Darkened with an irregular, focally notched border and color variation.</span><span className="block">Occasional itch; no bleeding or pain reported.</span></td>
                    <th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-normal text-[#667085]">Site</th>
                    <td className="border-b border-[#e0e4e9] p-3 align-top">Left shoulder</td>
                  </tr>
                  <tr>
                    <th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-medium text-[#475467]"><span className="flex items-center gap-3"><UsersRound className="size-4 shrink-0" aria-hidden="true" />History</span></th>
                    <td className="border-b border-r border-[#e0e4e9] p-3 align-top"><span className="block"><strong className="font-semibold text-[#243044]">Family history:</strong> Mother diagnosed with melanoma at age 57.</span><span className="block"><strong className="font-semibold text-[#243044]">Personal history:</strong> Atypical nevus documented in 2023.</span></td>
                    <th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-normal text-[#667085]">Lab SLA</th>
                    <td className="border-b border-[#e0e4e9] p-3 align-top">2–3 days</td>
                  </tr>
                  <tr>
                    <th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-medium text-[#475467]"><span className="flex items-center gap-3"><ClipboardList className="size-4 shrink-0" aria-hidden="true" />Symptoms</span></th>
                    <td className="border-b border-r border-[#e0e4e9] p-3 align-top">Occasional itch; no bleeding or pain reported.</td>
                    <th scope="row" className="border-b border-r border-[#e0e4e9] p-3 align-top font-normal text-[#667085]">Specimen handling</th>
                    <td className="border-b border-[#e0e4e9] p-3 align-top">Hudson Community Lab</td>
                  </tr>
                  <tr>
                    <th scope="row" className="border-r border-[#e0e4e9] p-3 align-top font-medium text-[#475467]"><span className="flex items-center gap-3"><ShieldCheck className="size-4 shrink-0" aria-hidden="true" />Confidence</span></th>
                    <td className="border-r border-[#e0e4e9] p-3 align-top">91% — Low procedure risk</td>
                    <th scope="row" className="border-r border-[#e0e4e9] p-3 align-top font-normal text-[#667085]">Approvals included</th>
                    <td className="p-3 align-top">Procedure plan, pathology order, biopsy aftercare, specimen &amp; result monitor, patient estimate, evidence-linked claim draft</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <details className="group mt-1">
            <summary className="mx-auto flex min-h-10 w-fit cursor-pointer list-none items-center gap-2 px-3 text-xs font-medium text-[#0f5cc4] outline-none hover:text-[#0b4ea9] focus-visible:ring-2 focus-visible:ring-[#7aa9e8] [&::-webkit-details-marker]:hidden">
              View full chart
              <ArrowRight className="size-3.5 transition-transform group-open:rotate-90" aria-hidden="true" />
            </summary>
            <div className="grid border-t border-[#e0e4e9] md:grid-cols-2 xl:grid-cols-4">
              <section className="border-b border-[#e0e4e9] p-4 md:border-r xl:border-b-0" aria-labelledby="clinical-chart-title">
                <ClipboardCheck className="size-4 text-[#167a83]" aria-hidden="true" />
                <h3 id="clinical-chart-title" className="mt-2 text-xs font-semibold">Clinical chart</h3>
                <ul className="mt-2 space-y-1 text-[11px] leading-5 text-[#667085]"><li>Adhesive tape allergy · active</li><li>Sertraline · current medication</li><li>No anticoagulant use recorded</li><li>Atypical nevus · 2023</li></ul>
              </section>
              <section className="border-b border-[#e0e4e9] p-4 xl:border-b-0 xl:border-r" aria-labelledby="communication-title">
                <MessageSquareText className="size-4 text-[#167a83]" aria-hidden="true" />
                <h3 id="communication-title" className="mt-2 text-xs font-semibold">Communication</h3>
                <p className="mt-2 text-[11px] leading-5 text-[#667085]">Sarah asked, “Will this leave a big scar?” A policy-grounded response is staged.</p>
              </section>
              <section className="border-b border-[#e0e4e9] p-4 md:border-r xl:border-b-0" aria-labelledby="diagnostic-plan-title">
                <Beaker className="size-4 text-[#167a83]" aria-hidden="true" />
                <h3 id="diagnostic-plan-title" className="mt-2 text-xs font-semibold">Diagnostic closure</h3>
                <p className="mt-2 text-[11px] leading-5 text-[#667085]">Provider review, patient acknowledgment, and surveillance disposition required.</p>
              </section>
              <section className="p-4" aria-labelledby="coverage-title">
                <FileText className="size-4 text-[#167a83]" aria-hidden="true" />
                <h3 id="coverage-title" className="mt-2 text-xs font-semibold">Coverage &amp; estimate</h3>
                <p className="mt-2 text-[11px] leading-5 text-[#667085]">Blue Horizon PPO · no prior authorization · $85 estimated patient responsibility.</p>
              </section>
            </div>
          </details>
        </section>
      </main>

      <Sheet open={modifyOpen} onOpenChange={changeModifyOpen}>
        <SheetContent id="modify-biopsy-plan" className="w-full overflow-y-auto bg-white sm:max-w-[480px]">
          <SheetHeader className="text-left">
            <SheetTitle>Modify biopsy plan</SheetTitle>
            <SheetDescription>Update the prepared recommendation before authorizing downstream work.</SheetDescription>
          </SheetHeader>
          <form onSubmit={saveRecommendation} className="mt-6 space-y-5">
            <div>
              <label htmlFor="biopsy-recommendation" className="text-sm font-medium text-[#172033]">Recommendation</label>
              <Textarea
                id="biopsy-recommendation"
                value={draftRecommendation}
                onChange={(event) => setDraftRecommendation(event.target.value)}
                className="mt-2 min-h-32 rounded-md border-[#cfd6df] text-sm leading-6"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => changeModifyOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={!draftRecommendation.trim()} className="bg-[#0f5cc4] text-white hover:bg-[#0b4ea9]">Save changes</Button>
            </div>
          </form>
        </SheetContent>
      </Sheet>
    </ScreenFrame>
  );
}

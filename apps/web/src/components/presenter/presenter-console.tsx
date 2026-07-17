"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowRight, Beaker, CheckCircle2, CircleDollarSign, Clock3, HeartPulse, KeyRound, MonitorPlay, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHeader, StatusBadge } from "@/components/product/page-elements";
import { useDemoSession } from "@/components/system/app-providers";
import { PageError, PageLoading } from "@/components/system/data-state";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { apiAction, endpoints } from "@/lib/api/client";
import type { Persona } from "@/lib/api/types";
import { formatInTimeZone } from "@/lib/date";

const chapters = [
  { number: 1, label: "Patient initiation", href: "/patient/start", persona: "patient", detail: "Concern → intake → eligibility → booking" },
  { number: 2, label: "Command center", href: "/command-center", persona: "clinical", detail: "Readiness, queues, pre-visit intelligence" },
  { number: 3, label: "AI-native encounter", href: "/encounters/sarah-biopsy", persona: "provider", detail: "Body map, ambient note, clinical proposals" },
  { number: 4, label: "Review and complete", href: "/encounters/sarah-biopsy/review", persona: "provider", detail: "Human approval and signed-record integrity" },
  { number: 5, label: "Pathology closure", href: "/pathology", persona: "provider", detail: "Result linkage, review, notification, follow-up" },
  { number: 6, label: "Revenue cycle", href: "/rcm", persona: "biller", detail: "Claim lifecycle, denial recovery, payments" },
  { number: 7, label: "MSO intelligence", href: "/mso", persona: "owner", detail: "Operating outcomes across the practice" },
] as const satisfies ReadonlyArray<{ number: number; label: string; href: string; persona: Persona; detail: string }>;

export function PresenterConsole() {
  const { setPersona } = useDemoSession();
  const { data, mode, error, refetch } = useDemoBootstrap();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [code, setCode] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [unlocking, setUnlocking] = useState(false);
  const [openingChapter, setOpeningChapter] = useState<number | null>(null);
  const [chapterError, setChapterError] = useState<string | null>(null);

  async function unlockPresenter() {
    setUnlocking(true);
    setInvalid(false);
    try {
      await apiAction(endpoints.demoSession, { persona: "owner", presenterCode: code });
      setPersona("owner");
      await refetch();
    } catch {
      setInvalid(true);
    } finally {
      setUnlocking(false);
    }
  }

  async function openChapter(chapter: (typeof chapters)[number]) {
    setOpeningChapter(chapter.number);
    setChapterError(null);
    try {
      await apiAction(endpoints.switchPersona, { persona: chapter.persona });
      setPersona(chapter.persona);
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
      router.push(chapter.href);
    } catch (chapterSwitchError) {
      setChapterError(
        chapterSwitchError instanceof Error
          ? chapterSwitchError.message
          : "The required demo persona could not be activated.",
      );
    } finally {
      setOpeningChapter(null);
    }
  }

  if (mode === "loading") return <PageLoading label="Loading presenter state" />;
  if (!data) return <PageError error={error} retry={refetch} />;

  if (!data.session.presenter) {
    return (
      <div className="mx-auto mt-16 max-w-md">
        <Card>
          <CardHeader><span className="mb-2 flex size-10 items-center justify-center rounded-full bg-primary/10 text-primary"><KeyRound className="size-5" /></span><CardTitle>Unlock presenter controls</CardTitle><p className="text-sm text-muted-foreground">Controls can mutate the canonical demo scenario and are hidden in normal product mode.</p></CardHeader>
          <CardContent className="space-y-4">
            <div><Label htmlFor="console-code">Presenter access code</Label><Input id="console-code" className="mt-2" type="password" value={code} onChange={(event) => setCode(event.target.value)} /></div>
            {invalid ? <Alert variant="destructive"><AlertDescription>That access code was not recognized.</AlertDescription></Alert> : null}
            <Button className="w-full" onClick={() => void unlockPresenter()} disabled={unlocking || !code}>{unlocking ? "Verifying…" : "Unlock controls"}</Button>
            <p className="text-[11px] leading-4 text-muted-foreground">Presenter capability is validated by the domain API and returned as a signed, HTTP-only session cookie.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Protected demo mode" title="Presenter console" description="Run the Sarah Mitchell story from a canonical seed, advance deterministic events, and inspect the health of every participating service." actions={<StatusBadge tone="success"><ShieldCheck className="size-3" /> Controls unlocked</StatusBadge>} />
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader className="border-b"><CardTitle className="flex items-center gap-2 text-base"><MonitorPlay className="size-4 text-primary" /> Demo chapters</CardTitle></CardHeader>
          <CardContent className="divide-y p-0">
            {chapterError ? <Alert variant="destructive" className="m-4"><AlertDescription>{chapterError} Stay on this page and try the chapter again.</AlertDescription></Alert> : null}
            {chapters.map((chapter) => (
              <Button
                key={chapter.number}
                type="button"
                variant="ghost"
                className="group flex h-auto w-full items-center justify-start gap-4 rounded-none px-5 py-4 text-left hover:bg-muted/40"
                disabled={openingChapter !== null}
                onClick={() => void openChapter(chapter)}
                data-testid={`presenter-chapter-${chapter.number}`}
              >
                <span className="flex size-8 items-center justify-center rounded-full border bg-background font-mono text-xs text-muted-foreground">{chapter.number}</span>
                <span className="min-w-0 flex-1"><span className="block text-sm font-semibold">{chapter.label}</span><span className="block truncate text-xs text-muted-foreground">{chapter.detail}</span></span>
                <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </Button>
            ))}
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-sm">Scenario state</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between"><span className="text-xs text-muted-foreground">Canonical clock</span><span className="font-mono text-xs">{formatInTimeZone(data.scenario.currentTime, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span></div>
              <Progress value={(data.scenario.chapter / 7) * 100} />
              <div className="flex items-center justify-between"><StatusBadge tone="info">Chapter {data.scenario.chapter} of 7</StatusBadge><span className="text-xs font-medium">{data.scenario.chapterLabel}</span></div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><HeartPulse className="size-4 text-primary" /> System health</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {data.health.map((service) => (
                <div key={service.id} className="flex items-center gap-3">
                  {service.id === "ai" ? <Activity className="size-4 text-violet-600" /> : service.id === "db" ? <CircleDollarSign className="size-4 text-primary" /> : service.id === "jobs" ? <Clock3 className="size-4 text-primary" /> : <Beaker className="size-4 text-primary" />}
                  <div className="min-w-0 flex-1"><p className="truncate text-xs font-medium">{service.service}</p><p className="text-[10px] text-muted-foreground">{service.latency}</p></div>
                  {service.status === "healthy" ? <CheckCircle2 className="size-4 text-emerald-600" /> : <StatusBadge tone="warning">Degraded</StatusBadge>}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

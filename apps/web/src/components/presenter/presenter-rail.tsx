"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Beaker,
  ChevronDown,
  ChevronUp,
  Clock3,
  FastForward,
  HeartPulse,
  ReceiptText,
  RotateCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { StatusBadge } from "@/components/product/page-elements";
import { useDemoSession } from "@/components/system/app-providers";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { apiAction, endpoints } from "@/lib/api/client";
import { useDemoBootstrap } from "@/lib/api/hooks";
import { selectDenialClaim } from "@/lib/api/selectors";
import type { ApiMode, DemoActionResult, DemoBootstrap } from "@/lib/api/types";
import { formatInTimeZone } from "@/lib/date";

const actions = [
  { id: "advance", label: "Advance 5 days", icon: FastForward, endpoint: endpoints.advanceTime },
  { id: "pathology", label: "Deliver pathology", icon: Beaker, endpoint: endpoints.triggerPathology },
  { id: "claim", label: "Deliver claim response", icon: ReceiptText, endpoint: endpoints.triggerClaimResponse },
  { id: "reset", label: "Reset canonical demo", icon: RotateCcw, endpoint: endpoints.resetDemo },
] as const;

type PresenterActionId = (typeof actions)[number]["id"];

export function presenterActionBlockedReason(
  actionId: PresenterActionId,
  data: DemoBootstrap | undefined,
  mode: ApiMode,
  claimTargetId: string | null,
): string | null {
  if (mode !== "live" || !data) return "The domain API must be connected before this action is available.";
  if (actionId === "reset") return null;

  const completionRecorded = Boolean(data.encounter?.completionReceipt);
  if (actionId === "pathology") {
    if (!completionRecorded) return "Complete clinician review first so a durable order and specimen exist.";
    if (data.pathology?.id || data.triggerIds?.pathologyResultId) return "The pathology result has already been delivered.";
    return null;
  }

  if (actionId === "claim") {
    if (!claimTargetId) {
      return completionRecorded
        ? "No presenter-authorized claim is available."
        : "Complete clinician review first so a durable claim exists.";
    }
    const claim = data.claims.find((item) => item.id === claimTargetId);
    if (!claim) return "The selected claim is not available in this workspace.";
    if (claim.status === "denied") return "Correct and resubmit the denied claim before delivering another payer response.";
    if (claim.status === "paid") return "This claim is already paid; no further payer transition is available.";
    return null;
  }

  const canonicalClaimId = data.triggerIds?.claimId;
  const canonicalClaim = canonicalClaimId
    ? data.claims.find((claim) => claim.id === canonicalClaimId)
    : null;
  if (!completionRecorded || !canonicalClaim) {
    return "Complete clinician review first; advancing now would reach timeline events without a durable claim or specimen.";
  }
  if (canonicalClaim.status === "denied") {
    return "Resolve the denial before advancing time so payer timeline events are not consumed out of order.";
  }
  if (canonicalClaim.status === "paid") return "The canonical payer timeline is complete.";
  return null;
}

export function PresenterRail({ onResetComplete = () => window.location.assign("/presenter") }: { onResetComplete?: () => void } = {}) {
  const [expanded, setExpanded] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [result, setResult] = useState<DemoActionResult | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, mode } = useDemoBootstrap();
  const { resetSessionState } = useDemoSession();
  const queryClient = useQueryClient();
  const pathname = usePathname();
  const routeClaimId = pathname.startsWith("/rcm/claims/") ? decodeURIComponent(pathname.split("/").at(-1) ?? "") : null;
  const denialClaimId = pathname === "/rcm/denials"
    ? selectDenialClaim(data?.claims ?? [])?.id ?? null
    : null;
  const claimTargetId = (routeClaimId && data?.claims.some((claim) => claim.id === routeClaimId) ? routeClaimId : null)
    ?? denialClaimId
    ?? data?.triggerIds?.claimId
    ?? null;

  async function runAction(action: (typeof actions)[number]) {
    if (mode !== "live" || !data) return;
    const blockedReason = presenterActionBlockedReason(action.id, data, mode, claimTargetId);
    if (blockedReason) {
      setActionError(blockedReason);
      return;
    }
    if (action.id === "claim" && !claimTargetId) {
      setActionError("No presenter-authorized claim ID was returned by the bootstrap endpoint.");
      return;
    }
    setPending(action.id);
    setResult(null);
    setActionError(null);
    try {
      const body = action.id === "advance"
        ? { days: 5 }
        : action.id === "pathology"
          ? {}
          : action.id === "claim"
            ? { entityId: claimTargetId }
            : { scenarioId: data.scenario.id };
      const nextResult = await apiAction(action.endpoint, body);
      if (action.id === "reset") {
        resetSessionState();
        queryClient.clear();
        onResetComplete();
        return;
      }
      setResult(nextResult);
      await queryClient.invalidateQueries({ queryKey: ["demo-bootstrap"] });
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Action failed.");
    } finally {
      setPending(null);
    }
  }

  if (!expanded) {
    return (
      <Button
        data-testid="presenter-rail-toggle"
        className="fixed bottom-4 right-4 z-50 h-11 rounded-full border border-primary/20 px-4 shadow-xl"
        onClick={() => setExpanded(true)}
      >
        <ShieldCheck className="size-4" /> Presenter <ChevronUp className="size-3.5" />
      </Button>
    );
  }

  return (
    <Card className="fixed bottom-4 right-4 z-50 w-[min(380px,calc(100vw-2rem))] border-primary/25 bg-card/98 shadow-2xl backdrop-blur" data-testid="presenter-rail">
      <CardHeader className="flex-row items-start justify-between space-y-0 pb-3">
        <div>
          <CardTitle className="flex items-center gap-2 text-sm"><ShieldCheck className="size-4 text-primary" /> Presenter rail</CardTitle>
          <p className="mt-1 text-[11px] text-muted-foreground">{data?.scenario.chapterLabel ?? "Demo scenario"} · Chapter {data?.scenario.chapter ?? 3}</p>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon-xs" onClick={() => setExpanded(false)} aria-label="Collapse presenter rail"><ChevronDown /></Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between rounded-md bg-muted/60 px-3 py-2">
          <div className="flex items-center gap-2 text-xs"><Clock3 className="size-3.5" /> Scenario time</div>
          <span className="font-mono text-[10px]">{data ? formatInTimeZone(data.scenario.currentTime, data.organization.timezone, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "Loading"}</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {actions.map((action) => {
            const Icon = action.icon;
            const blockedReason = presenterActionBlockedReason(action.id, data, mode, claimTargetId);
            return (
              <Button
                key={action.id}
                variant="outline"
                size="sm"
                className="justify-start text-xs"
                disabled={pending !== null || Boolean(blockedReason)}
                onClick={() => void runAction(action)}
                data-testid={`presenter-${action.id}`}
                aria-describedby={blockedReason ? `presenter-${action.id}-reason` : undefined}
                title={blockedReason ?? undefined}
              >
                <Icon className="size-3.5" /> {pending === action.id ? "Working…" : action.label}
              </Button>
            );
          })}
        </div>
        {mode === "live" ? actions.map((action) => {
          const blockedReason = presenterActionBlockedReason(action.id, data, mode, claimTargetId);
          return blockedReason ? <p key={action.id} id={`presenter-${action.id}-reason`} data-testid={`presenter-${action.id}-reason`} className="text-[10px] leading-4 text-muted-foreground"><span className="font-semibold text-foreground">{action.label}:</span> {blockedReason}</p> : null;
        }) : null}
        {result ? (
          <Alert className="border-emerald-200 bg-emerald-50" data-testid="presenter-action-receipt">
            <AlertDescription className="text-xs">{result.message}</AlertDescription>
          </Alert>
        ) : null}
        {actionError ? <Alert variant="destructive"><AlertDescription className="text-xs">{actionError}</AlertDescription></Alert> : null}
        {mode !== "live" ? <Alert className="border-amber-200 bg-amber-50"><AlertDescription className="text-xs">Presenter mutations are disabled while the domain API is unavailable.</AlertDescription></Alert> : null}
        <Separator />
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Demo health</span>
            {mode === "live" ? <StatusBadge tone="success">API live</StatusBadge> : <StatusBadge tone="danger">Unavailable</StatusBadge>}
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            {(data?.health ?? []).map((service) => (
              <div key={service.id} className="flex items-center gap-2 text-[11px]">
                {service.id === "ai" ? <Sparkles className="size-3 text-violet-600" /> : service.id === "api" ? <HeartPulse className="size-3 text-primary" /> : <Activity className="size-3 text-primary" />}
                <span className="truncate">{service.service}</span>
                <span className={`ml-auto size-1.5 rounded-full ${service.status === "healthy" ? "bg-emerald-500" : "bg-amber-500"}`} />
              </div>
            ))}
          </div>
        </div>
        <Button asChild variant="ghost" size="sm" className="w-full text-xs"><Link href="/presenter">Open full presenter console</Link></Button>
      </CardContent>
    </Card>
  );
}

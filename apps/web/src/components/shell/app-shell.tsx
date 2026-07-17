"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  Beaker,
  CalendarDays,
  ChevronDown,
  CircleDollarSign,
  HeartPulse,
  Menu,
  MessageSquareText,
  Settings2,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type PropsWithChildren } from "react";

import { PresenterRail } from "@/components/presenter/presenter-rail";
import { StatusBadge } from "@/components/product/page-elements";
import { useDemoSession } from "@/components/system/app-providers";
import { PageLoading } from "@/components/system/data-state";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { demoBootstrapQueryKey, useDemoBootstrap } from "@/lib/api/hooks";
import { ApiError, apiAction, apiRequest, endpoints } from "@/lib/api/client";
import type { Persona } from "@/lib/api/types";
import type { DemoBootstrap } from "@/lib/api/types";
import { replaceWithLogin } from "@/lib/auth/session-lifecycle";
import { formatInTimeZone } from "@/lib/date";
import { cn } from "@/lib/utils";

const navigation = [
  {
    label: "Platform",
    items: [
      { href: "/command-center", label: "Today", icon: CalendarDays, roles: ["provider", "clinical", "biller", "owner"] },
      { href: "/patients", label: "Patients", icon: UsersRound, roles: ["provider", "clinical", "biller", "owner"] },
      { href: "/schedule", label: "Schedule", icon: CalendarDays, roles: ["provider", "clinical", "biller", "owner"] },
      { href: "/messages", label: "Inbox", icon: MessageSquareText, queueId: "messages", roles: ["provider", "clinical", "biller", "owner"] },
      { href: "/pathology", label: "Results", icon: Beaker, queueId: "path", roles: ["provider", "clinical", "biller", "owner"] },
      { href: "/rcm", label: "Revenue", icon: CircleDollarSign, queueId: "claims", roles: ["provider", "clinical", "biller", "owner"] },
      { href: "/mso", label: "Operations", icon: Settings2, roles: ["provider", "clinical", "biller", "owner"] },
    ],
  },
] as const;

const personaDestinations: Record<Persona, string> = {
  patient: "/patient/start",
  provider: "/command-center",
  clinical: "/command-center",
  biller: "/rcm",
  owner: "/mso",
};

export function Brand({ href = "/command-center", onNavigate, inverse = false }: { href?: string; onNavigate?: () => void; inverse?: boolean }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2.5", inverse && "text-white")} aria-label="Ambrosia home" onClick={onNavigate}>
      <span className={cn("flex size-9 items-center justify-center rounded-xl border shadow-sm", inverse ? "border-white/25 bg-white/10 text-white" : "border-primary/15 bg-primary text-primary-foreground")}>
        <HeartPulse className="size-4.5" />
      </span>
      <span>
        <span className="block text-sm font-semibold tracking-[-0.025em]">Ambrosia</span>
        <span className={cn("block text-[10px] font-medium uppercase tracking-[0.2em]", inverse ? "text-white/66" : "text-muted-foreground")}>Health</span>
      </span>
    </Link>
  );
}

function MainNavigation({
  persona,
  queueCounts,
  mobile = false,
  onNavigate,
}: {
  persona: Persona;
  queueCounts: Record<string, number>;
  mobile?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary navigation" className="space-y-6">
      {navigation.map((section) => (
        <div key={section.label}>
          <p className="sr-only">{section.label}</p>
          <div className="space-y-0.5">
            {section.items.filter((item) => (item.roles as readonly Persona[]).includes(persona)).map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "group flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-white/72 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70",
                    active && "bg-white/16 text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]",
                    mobile && "h-11",
                  )}
                  aria-current={active ? "page" : undefined}
                  onClick={onNavigate}
                >
                  <Icon className={cn("size-4", active ? "text-white" : "text-white/72")} />
                  <span className="flex-1">{item.label}</span>
                  {"queueId" in item && item.queueId && queueCounts[item.queueId] ? (
                    <span className="flex min-w-5 items-center justify-center rounded-full bg-white/12 px-1.5 font-mono text-[9px] tabular-nums text-white/80">{queueCounts[item.queueId]}</span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

function PersonaMenu({ allowPersonaSwitch }: { allowPersonaSwitch: boolean }) {
  const { persona, setPersona, endSession } = useDemoSession();
  const { data } = useDemoBootstrap();
  const queryClient = useQueryClient();
  const activePersona = data?.session.authenticated ? data.session.persona : persona;
  const current = data?.personas.find((item) => item.id === activePersona);
  const [switchError, setSwitchError] = useState(false);
  const [logoutPending, setLogoutPending] = useState(false);

  async function selectPersona(nextPersona: Persona) {
    setSwitchError(false);
    try {
      await apiAction(endpoints.switchPersona, { persona: nextPersona });
      setPersona(nextPersona);
      window.location.assign(personaDestinations[nextPersona]);
    } catch {
      setSwitchError(true);
    }
  }

  async function logout() {
    setSwitchError(false);
    setLogoutPending(true);
    try {
      await apiRequest(endpoints.logout, { method: "POST" });
      await queryClient.cancelQueries({ queryKey: demoBootstrapQueryKey });
      endSession();
      queryClient.setQueryData<DemoBootstrap>(demoBootstrapQueryKey, (current) => current ? {
        ...current,
        session: { ...current.session, authenticated: false, presenter: false },
      } : undefined);
      replaceWithLogin();
    } catch {
      setSwitchError(true);
      setLogoutPending(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-auto justify-start gap-2 px-2 py-1.5" aria-label={allowPersonaSwitch ? "Switch demo persona" : "Account menu"}>
          <Avatar className="size-8 border bg-card">
            <AvatarFallback className="bg-primary/8 text-xs font-semibold text-primary">{current?.initials ?? "MC"}</AvatarFallback>
          </Avatar>
          <span className="hidden min-w-0 text-left sm:block">
            <span className="block truncate text-xs font-semibold text-foreground">{current?.name ?? "Signed-in user"}</span>
            <span className="block truncate text-[11px] font-normal text-muted-foreground">{current?.title ?? "Dermatologist"}</span>
          </span>
          <ChevronDown className="size-3.5 text-muted-foreground" />
          {switchError ? <span className="sr-only">Persona switch failed</span> : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>{allowPersonaSwitch ? "Demo personas" : current?.name ?? "Account"}</DropdownMenuLabel>
        {allowPersonaSwitch ? <>
          <DropdownMenuSeparator />
          {data?.personas.map((item) => (
            <DropdownMenuItem key={item.id} onSelect={() => void selectPersona(item.id)} className="gap-3 py-2.5">
              <Avatar className="size-7"><AvatarFallback className="text-[10px]">{item.initials}</AvatarFallback></Avatar>
              <span className="flex-1"><span className="block text-xs font-medium">{item.name}</span><span className="block text-[11px] text-muted-foreground">{item.title}</span></span>
              {item.id === activePersona ? <span className="size-1.5 rounded-full bg-primary" /> : null}
            </DropdownMenuItem>
          ))}
        </> : null}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={logoutPending}
          onSelect={() => void logout()}
          data-testid="exit-demo"
        >
          {logoutPending ? "Signing out…" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function PatientHeader() {
  const { persona } = useDemoSession();
  const { data, mode } = useDemoBootstrap();
  const activePersona = data?.session.authenticated ? data.session.persona : persona;
  const current = data?.personas.find((item) => item.id === activePersona);
  const presenterActive = mode === "live" && Boolean(data?.session.presenter);
  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6">
        <Brand href="/patient/start" />
        <div className="flex items-center gap-2">
          {mode === "loading" ? <StatusBadge tone="info">Connecting</StatusBadge> : mode === "error" ? <StatusBadge tone="danger">Session unavailable</StatusBadge> : data?.session.authenticated ? <StatusBadge tone="success">Secure session</StatusBadge> : <StatusBadge tone="warning">Sign in required</StatusBadge>}
          {data?.session.authenticated ? <PersonaMenu allowPersonaSwitch={presenterActive} /> : <span className="text-xs font-medium text-muted-foreground">{current?.name ?? "Signed-in patient"}</span>}
        </div>
      </div>
    </header>
  );
}

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const { persona, sessionLifecycle } = useDemoSession();
  const { data, mode, error } = useDemoBootstrap();
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const activePersona = data?.session.authenticated ? data.session.persona : persona;
  const presenterActive = mode === "live" && Boolean(data?.session.presenter);
  const isPatientSurface = pathname.startsWith("/patient/") || activePersona === "patient";
  const isPlatformSurface = ["/command-center", "/patients", "/schedule", "/messages", "/pathology", "/rcm", "/mso"].some((route) => pathname === route || (route === "/patients" && pathname.startsWith("/patients/")));
  const queueCounts = Object.fromEntries((data?.queues ?? []).map((queue) => [queue.id, queue.count]));
  const scenarioDate = data ? formatInTimeZone(data.scenario.currentTime, data.organization.timezone, { month: "short", day: "numeric", year: "numeric" }) : null;
  const unauthenticated = sessionLifecycle === "ended" || (mode === "live" && data && !data.session.authenticated) || (error instanceof ApiError && error.status === 401);

  useEffect(() => {
    if (unauthenticated) replaceWithLogin();
  }, [unauthenticated]);

  if (unauthenticated) {
    return <main className="mx-auto w-full max-w-xl px-6 py-12"><PageLoading label="Returning to sign in" /></main>;
  }

  if (sessionLifecycle === "checking" || mode === "loading") {
    return <main className="mx-auto w-full max-w-xl px-6 py-12"><PageLoading label="Loading your secure workspace" /></main>;
  }

  if (isPatientSurface) {
    return (
      <div className="min-h-screen bg-[var(--patient-background)]">
        <PatientHeader />
        <main>{children}</main>
        {presenterActive ? <PresenterRail /> : null}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#fbfaf6] text-foreground">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 bg-[#123f30] text-white lg:flex lg:flex-col">
        <div className="flex h-[4.75rem] items-center px-5"><Brand href="/command-center" inverse /></div>
        <Separator className="bg-white/10" />
        <ScrollArea className="flex-1 px-3 py-5"><MainNavigation persona={activePersona} queueCounts={queueCounts} /></ScrollArea>
        <div className="border-t border-white/10 p-3">
          {presenterActive ? <Link href="/presenter" className="flex items-center gap-2 rounded-md px-3 py-2 text-xs text-white/70 hover:bg-white/10 hover:text-white">
            <ShieldCheck className="size-4" /> Presenter controls
          </Link> : null}
          <div className="mt-2 rounded-lg border border-white/12 bg-white/7 p-3">
            <div className="flex items-center gap-2 text-[11px] font-medium text-white"><span className="flex size-5 items-center justify-center rounded-full border border-white/25"><ShieldCheck className="size-3" /></span> Ambrosia is operating</div>
            <p className="mt-2 text-[10px] leading-4 text-white/60">309 journeys advancing.<br />Clinical decisions always wait for you.</p>
          </div>
          <div className="px-3 pb-2 pt-4"><p className="text-xs font-semibold text-white">Midtown Dermatology</p><p className="mt-1 text-[10px] text-white/55">New York, NY</p></div>
        </div>
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 grid h-[4.75rem] grid-cols-[1fr_auto] items-center gap-5 border-b border-[#dce3db] bg-[#fffefa]/94 px-4 backdrop-blur sm:px-6 lg:grid-cols-[1fr_auto_1fr] lg:px-7">
          <div className="flex items-center gap-3">
            <Sheet open={mobileNavigationOpen} onOpenChange={setMobileNavigationOpen}>
              <SheetTrigger asChild><Button variant="outline" size="icon-sm" className="lg:hidden" aria-label="Open navigation"><Menu /></Button></SheetTrigger>
              <SheetContent side="left" className="w-72 border-0 bg-[#123f30] p-0 text-white">
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <div className="flex h-[4.75rem] items-center px-5"><Brand href="/command-center" inverse onNavigate={() => setMobileNavigationOpen(false)} /></div>
                <Separator className="bg-white/10" />
                <div className="p-4"><MainNavigation persona={activePersona} queueCounts={queueCounts} mobile onNavigate={() => setMobileNavigationOpen(false)} /></div>
              </SheetContent>
            </Sheet>
            <div className="hidden sm:block"><p className="text-sm font-semibold tracking-[-0.02em] text-[#15392c]">Midtown Dermatology</p><p className="mt-0.5 text-[10px] text-[#718078]">New York, NY</p></div>
          </div>
          <div className="hidden text-center text-xs font-medium text-[#3e554a] lg:block">{isPlatformSurface ? "Jul 17, 2026" : (scenarioDate ?? "Jul 17, 2026")}</div>
          <div className="flex items-center justify-end gap-3">
            <div className="hidden items-center gap-2 text-right xl:flex"><ShieldCheck className="size-5 text-[#1f5b42]" /><div><p className="text-[10px] font-semibold text-[#284c3b]">Clinical decisions wait for you</p><p className="mt-0.5 text-[9px] text-[#718078]">Everything else keeps moving</p></div></div>
            {data?.session.authenticated ? <PersonaMenu allowPersonaSwitch={presenterActive} /> : null}
          </div>
        </header>
        <main className={cn("mx-auto min-h-[calc(100vh-4.75rem)]", isPlatformSurface ? "max-w-none p-0" : "max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8")}>{children}</main>
      </div>
      {presenterActive ? <PresenterRail /> : null}
    </div>
  );
}

"use client";

import {
  Beaker,
  CalendarDays,
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
import { useState, type PropsWithChildren } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/", label: "Today", icon: CalendarDays },
  { href: "/patients", label: "Patients", icon: UsersRound },
  { href: "/schedule", label: "Schedule", icon: CalendarDays },
  { href: "/messages", label: "Inbox", icon: MessageSquareText },
  { href: "/pathology", label: "Results", icon: Beaker },
  { href: "/rcm", label: "Revenue", icon: CircleDollarSign },
  { href: "/mso", label: "Operations", icon: Settings2 },
] as const;

export function Brand({ onNavigate, inverse = false }: { onNavigate?: () => void; inverse?: boolean }) {
  return (
    <Link href="/" className={cn("flex items-center gap-2.5", inverse && "text-white")} aria-label="Ambrosia home" onClick={onNavigate}>
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

function MainNavigation({ mobile = false, onNavigate }: { mobile?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary navigation">
      <div className="space-y-0.5">
        {navigation.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname === item.href || pathname.startsWith(`${item.href}/`);
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
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

function ClinicianIdentity() {
  return (
    <div className="flex items-center gap-2 px-2 py-1.5" aria-label="Current dermatologist">
      <Avatar className="size-8 border bg-card">
        <AvatarFallback className="bg-primary/8 text-xs font-semibold text-primary">MC</AvatarFallback>
      </Avatar>
      <span className="hidden min-w-0 text-left sm:block">
        <span className="block truncate text-xs font-semibold text-foreground">Dr. Maya Chen</span>
        <span className="block truncate text-[11px] font-normal text-muted-foreground">Dermatologist</span>
      </span>
    </div>
  );
}

export function AppShell({ children }: PropsWithChildren) {
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#fbfaf6] text-foreground">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 bg-[#123f30] text-white lg:flex lg:flex-col">
        <div className="flex h-[4.75rem] items-center px-5"><Brand inverse /></div>
        <Separator className="bg-white/10" />
        <ScrollArea className="flex-1 px-3 py-5"><MainNavigation /></ScrollArea>
        <div className="border-t border-white/10 p-3">
          <div className="rounded-lg border border-white/12 bg-white/7 p-3">
            <div className="flex items-center gap-2 text-[11px] font-medium text-white"><span className="flex size-5 items-center justify-center rounded-full border border-white/25"><ShieldCheck className="size-3" /></span> Ambrosia is operating</div>
            <p className="mt-2 text-[10px] leading-4 text-white/60">Intake, scheduling, follow-up, and revenue are moving. Clinical judgment waits for you.</p>
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
                <div className="flex h-[4.75rem] items-center px-5"><Brand inverse onNavigate={() => setMobileNavigationOpen(false)} /></div>
                <Separator className="bg-white/10" />
                <div className="p-4"><MainNavigation mobile onNavigate={() => setMobileNavigationOpen(false)} /></div>
              </SheetContent>
            </Sheet>
            <div className="hidden sm:block"><p className="text-sm font-semibold tracking-[-0.02em] text-[#15392c]">Midtown Dermatology</p><p className="mt-0.5 text-[10px] text-[#718078]">New York, NY</p></div>
          </div>
          <div className="hidden text-center text-xs font-medium text-[#3e554a] lg:block">Jul 17, 2026</div>
          <div className="flex items-center justify-end gap-3">
            <div className="hidden items-center gap-2 text-right xl:flex"><ShieldCheck className="size-5 text-[#1f5b42]" /><div><p className="text-[10px] font-semibold text-[#284c3b]">Clinical decisions wait for you</p><p className="mt-0.5 text-[9px] text-[#718078]">Administrative work keeps moving</p></div></div>
            <ClinicianIdentity />
          </div>
        </header>
        <main className="mx-auto min-h-[calc(100vh-4.75rem)] max-w-none p-0">{children}</main>
      </div>
    </div>
  );
}

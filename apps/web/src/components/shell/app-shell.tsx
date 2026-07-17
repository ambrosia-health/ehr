"use client";

import { ChevronDown, Flower, Menu, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type PropsWithChildren } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

import { AmbrosiaCommand } from "./ambrosia-command";

const navigation = [
  { href: "/", label: "Today" },
  { href: "/patients", label: "Patients" },
  { href: "/practice", label: "Practice" },
] as const;

interface BrandProps {
  onNavigate?: () => void;
}

export function Brand({ onNavigate }: BrandProps) {
  return (
    <Link
      href="/"
      className="flex shrink-0 items-center gap-3 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-4"
      aria-label="Ambrosia home"
      onClick={onNavigate}
    >
      <Flower className="size-8 text-primary" strokeWidth={2.5} aria-hidden="true" />
      <span className="text-lg font-semibold tracking-[-0.035em]">Ambrosia</span>
    </Link>
  );
}

interface MainNavigationProps {
  mobile?: boolean;
  onNavigate?: () => void;
}

function MainNavigation({ mobile = false, onNavigate }: MainNavigationProps) {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary navigation"
      className={cn(mobile ? "grid gap-1" : "flex h-full items-stretch gap-2")}
    >
      {navigation.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname === item.href || pathname.startsWith(`${item.href}/`);

        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            onClick={onNavigate}
            className={cn(
              "text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              mobile
                ? "flex h-11 items-center rounded-md border-l-[3px] border-transparent px-4 text-muted-foreground hover:bg-muted hover:text-foreground"
                : "flex h-[4.5rem] items-center border-b-[3px] border-transparent px-3 pt-[3px] text-muted-foreground hover:text-foreground",
              active && (mobile
                ? "border-primary bg-secondary text-primary"
                : "border-primary text-foreground"),
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function ClinicianIdentity() {
  return (
    <div className="flex items-center gap-3" aria-label="Current dermatologist">
      <Avatar className="size-10 border border-border bg-card">
        <AvatarFallback className="bg-card text-xs font-medium text-foreground">MC</AvatarFallback>
      </Avatar>
      <span className="min-w-0">
        <span className="block truncate text-[13px] font-semibold leading-5 text-foreground">Dr. Maya Chen</span>
        <span className="block truncate text-[11px] leading-4 text-muted-foreground">Midtown Dermatology</span>
      </span>
      <ChevronDown className="ml-1 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
    </div>
  );
}

export function AppShell({ children }: PropsWithChildren) {
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  useEffect(() => {
    function openCommand(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
    }

    window.addEventListener("keydown", openCommand);
    return () => window.removeEventListener("keydown", openCommand);
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 h-16 border-b border-border bg-card lg:h-[4.5rem]">
        <div className="flex h-full w-full items-center px-4 sm:px-6 lg:px-7">
          <Brand />

          <div className="ml-12 hidden h-full lg:block">
            <MainNavigation />
          </div>

          <div className="ml-auto hidden items-center lg:flex">
            <ClinicianIdentity />
            <span className="sr-only">Press Command K to ask Ambrosia</span>
          </div>

          <Sheet open={mobileNavigationOpen} onOpenChange={setMobileNavigationOpen}>
            <SheetTrigger asChild>
              <Button className="ml-auto lg:hidden" variant="outline" size="icon" aria-label="Open navigation">
                <Menu className="size-4" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[19rem] border-l border-border bg-card p-0 sm:max-w-[19rem]">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <div className="flex h-full flex-col px-5 py-6">
                <Brand onNavigate={() => setMobileNavigationOpen(false)} />
                <div className="mt-9">
                  <MainNavigation mobile onNavigate={() => setMobileNavigationOpen(false)} />
                </div>
                <div className="mt-6 border-t border-border pt-6">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 w-full justify-start rounded-md text-primary"
                    onClick={() => {
                      setMobileNavigationOpen(false);
                      setCommandOpen(true);
                    }}
                  >
                    <Sparkles className="size-4" />
                    Ask Ambrosia
                  </Button>
                </div>
                <div className="mt-auto border-t border-border pt-5">
                  <ClinicianIdentity />
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      <div className="min-h-[calc(100vh-4rem)] lg:min-h-[calc(100vh-4.5rem)]">{children}</div>

      <AmbrosiaCommand open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  );
}

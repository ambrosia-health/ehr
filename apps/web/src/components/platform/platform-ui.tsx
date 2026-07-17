"use client";

import { Check, CheckCircle2, Circle, Clock3, Octagon, Search, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import type { JourneyStatus } from "./platform-fixtures";

export function ScreenFrame({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("min-h-screen bg-background text-foreground", className)}>{children}</div>;
}

const statusConfig: Record<JourneyStatus, { icon: typeof Check; label: string; className: string }> = {
  complete: { icon: Check, label: "Completed", className: "border-primary bg-primary text-primary-foreground" },
  moving: { icon: Circle, label: "Advancing", className: "border-primary/25 bg-secondary text-primary" },
  waiting: { icon: Clock3, label: "Waiting", className: "border-border bg-muted text-muted-foreground" },
  human: { icon: Octagon, label: "Waiting for you", className: "border-decision/30 bg-decision-muted text-decision" },
  risk: { icon: TriangleAlert, label: "At risk", className: "border-safety/30 bg-safety-muted text-safety" },
};

export function StatusPill({ status, children }: { status: JourneyStatus; children: ReactNode }) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <span className={cn("inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-[10px] font-semibold", config.className)}>
      <Icon className="size-3" aria-hidden="true" />
      {children}
    </span>
  );
}

export function PatientMark({ initials, size = "md" }: { initials: string; size?: "sm" | "md" | "lg" }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full border border-primary/15 bg-secondary font-semibold text-secondary-foreground",
        size === "sm" && "size-7 text-[10px]",
        size === "md" && "size-10 text-xs",
        size === "lg" && "size-14 text-sm",
      )}
    >
      {initials}
    </span>
  );
}

export function SearchField({ value, onChange, placeholder = "Search" }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label="Search patients"
        className="h-11 border-border bg-card pl-9 shadow-none"
      />
    </div>
  );
}

export function ApprovalReceipt({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-secondary p-4 text-sm text-secondary-foreground">
      <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

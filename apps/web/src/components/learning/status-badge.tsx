import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  label: string;
  tone?: "neutral" | "good" | "warning" | "danger" | "evidence";
}

const toneClasses = {
  neutral: "border-border bg-muted text-muted-foreground",
  good: "border-evidence/25 bg-evidence-muted text-evidence-foreground",
  warning: "border-decision/25 bg-decision-muted text-decision",
  danger: "border-safety/25 bg-safety-muted text-safety",
  evidence: "border-primary/20 bg-secondary text-secondary-foreground",
} as const;

export function StatusBadge({ label, tone = "neutral" }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold tracking-wide",
        toneClasses[tone],
      )}
    >
      {label}
    </span>
  );
}

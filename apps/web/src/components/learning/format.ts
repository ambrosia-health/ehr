import type { ModelIdentity } from "@/components/learning/types";

export function formatLabel(value: string): string {
  return value
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[._-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Not finished";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "None";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  if (typeof value === "object") {
    return Object.entries(value)
      .map(([key, nested]) => `${formatLabel(key)}: ${formatValue(nested)}`)
      .join(" · ");
  }
  return String(value);
}

export function formatModel(model: ModelIdentity): string {
  if (!model) return "No model recorded";
  if (typeof model === "string") return model;
  if (model.provider && model.model) return `${model.provider} / ${model.model}`;
  return model.model ?? model.provider ?? "No model recorded";
}

export function formatReward(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

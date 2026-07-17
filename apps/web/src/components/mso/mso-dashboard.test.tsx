import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MsoDashboard } from "@/components/mso/mso-dashboard";
import type { DemoBootstrap } from "@/lib/api/types";
import { bootstrapFixture } from "@/test/fixtures/bootstrap";

const metricLabels = {
  conversion: "Digital intake conversion",
  noshow: "No-show rate",
  response: "Message response time",
  satisfaction: "Message read rate",
  sign: "Time to sign",
  path_open: "Open pathology",
  path_closure: "Pathology closure time",
  doc: "Documentation support",
  avoided: "Staff work avoided",
  accept: "Claim acceptance",
  denial: "Denial rate",
  ar: "Days in A/R",
  revenue: "Revenue per visit",
} as const;

const ownerBootstrap: DemoBootstrap = {
  ...bootstrapFixture,
  session: { authenticated: true as const, persona: "owner" as const, presenter: false },
  metrics: Object.entries(metricLabels).map(([id, label]) => ({
    id,
    label,
    value: "1",
    change: "Calculated from current records",
    target: "at least 1",
    score: 100,
    tone: "success" as const,
    supportingCount: "1 durable record",
    assumption: "Current tenant-scoped records.",
    source: `source_${id}`,
  })),
};

vi.mock("@/lib/api/hooks", () => ({
  useDemoBootstrap: () => ({ data: ownerBootstrap, mode: "live", error: null, refetch: vi.fn() }),
}));

describe("MsoDashboard", () => {
  it("renders every backend metric in its intended group", () => {
    render(<MsoDashboard />);
    expect(screen.getByRole("heading", { name: "Growth & access" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Clinical operations" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Revenue performance" })).toBeVisible();
    for (const label of Object.values(metricLabels)) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText("13").length).toBeGreaterThan(0);
  });

  it("renders missing response, signing, and pathology samples as neutral insufficient data", () => {
    const missingIds = ["response", "sign", "path_closure"];
    const originals = missingIds.map((id) => {
      const metric = ownerBootstrap.metrics.find((item) => item.id === id)!;
      return { metric, value: metric.value, score: metric.score, tone: metric.tone, change: metric.change };
    });
    for (const { metric } of originals) {
      metric.value = null;
      metric.score = null;
      metric.tone = "success";
      metric.change = "Calculated from current records";
    }

    try {
      render(<MsoDashboard />);
      for (const id of missingIds) {
        const card = screen.getByTestId(`mso-metric-${id}`);
        expect(card).toHaveAttribute("data-status", "insufficient-data");
        expect(within(card).getByText("N/A")).toBeVisible();
        expect(within(card).getByText("Insufficient data")).toBeVisible();
      }
    } finally {
      for (const { metric, value, score, tone, change } of originals) Object.assign(metric, { value, score, tone, change });
    }
  });

  it("only calls a metric on target when it meets the full target", () => {
    const scoredIds = ["conversion", "noshow", "response"];
    const originals = scoredIds.map((id) => {
      const metric = ownerBootstrap.metrics.find((item) => item.id === id)!;
      return { metric, score: metric.score };
    });
    originals[0].metric.score = 100;
    originals[1].metric.score = 90;
    originals[2].metric.score = 69;

    try {
      render(<MsoDashboard />);
      expect(within(screen.getByTestId("mso-metric-conversion")).getByText("On target")).toBeVisible();
      expect(within(screen.getByTestId("mso-metric-noshow")).getByText("Near target")).toBeVisible();
      expect(within(screen.getByTestId("mso-metric-response")).getByText("Needs action")).toBeVisible();
    } finally {
      for (const { metric, score } of originals) metric.score = score;
    }
  });
});

import { describe, expect, it } from "vitest";

import { selectDenialClaim } from "@/lib/api/selectors";
import type { DemoBootstrap } from "@/lib/api/types";

type Claim = DemoBootstrap["claims"][number];

function denialClaim(
  id: string,
  denialStatus: string,
  recovery: Claim["denial"] extends infer Denial | undefined
    ? Denial extends { recovery: infer Recovery }
      ? Recovery
      : never
    : never = null,
): Claim {
  return {
    id,
    denial: {
      id: `${id}-denial`,
      status: denialStatus,
      recovery,
    },
  } as Claim;
}

describe("selectDenialClaim", () => {
  it("prioritizes an actionable open denial over older cohort history", () => {
    const historical = denialClaim("historical", "resolved", {
      appealId: "appeal-old",
      status: "submitted",
      outcome: null,
      recoveredAmount: 0,
      submittedAt: null,
    });
    const actionable = denialClaim("actionable", "open");

    expect(selectDenialClaim([historical, actionable])?.id).toBe("actionable");
  });

  it("keeps the explicitly resubmitted denial selected after it resolves", () => {
    const historical = denialClaim("historical", "resolved", null);
    const resubmitted = denialClaim("resubmitted", "resolved", {
      appealId: "appeal-new",
      status: "submitted",
      outcome: null,
      recoveredAmount: 0,
      submittedAt: "2026-07-16T14:00:00Z",
    });

    expect(selectDenialClaim([historical, resubmitted])?.id).toBe("resubmitted");
  });
});

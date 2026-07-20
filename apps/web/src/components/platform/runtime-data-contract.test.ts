import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const runtimeSources = [
  "src/components/platform/today-screen.tsx",
  "src/components/platform/patients-screen.tsx",
  "src/components/platform/patient-agent-screen.tsx",
  "src/components/platform/practice-screen.tsx",
  "src/components/platform/product-workspace-provider.tsx",
  "src/components/shell/app-shell.tsx",
  "src/components/shell/ambrosia-command.tsx",
];

describe("clinician runtime data contract", () => {
  it("has no presentation-fixture imports or direct fetch calls", () => {
    const source = runtimeSources.map((path) => readFileSync(resolve(process.cwd(), path), "utf8")).join("\n");

    expect(source).not.toContain("platform-fixtures");
    expect(source).not.toMatch(/\bfetch\s*\(/);
    expect(source).not.toMatch(/Alex Rivera|Natalie Wong|Jordan Lee|312 active|309 patient/);
  });

  it("does not encode managed API origins in the Next.js router", () => {
    const config = readFileSync(resolve(process.cwd(), "next.config.ts"), "utf8");

    expect(config).toContain("process.env.AMBROSIA_API_ORIGIN");
    expect(config).not.toContain("modal.run");
    expect(config).not.toContain("productionHosts");
  });
});

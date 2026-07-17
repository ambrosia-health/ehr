import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.NEXT_PUBLIC_APP_URL;
if (!baseURL?.startsWith("https://")) {
  throw new Error("NEXT_PUBLIC_APP_URL must be an HTTPS deployment for hosted E2E.");
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  expect: { timeout: 30_000 },
  use: {
    baseURL,
    actionTimeout: 30_000,
    navigationTimeout: 45_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
});

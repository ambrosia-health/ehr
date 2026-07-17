import { expect, test } from "@playwright/test";

const legacyRoutes = [
  "/login",
  "/command-center",
  "/patient/start",
  "/presenter",
  "/encounters/sarah-biopsy",
  "/rcm/denials",
];

test("opens directly into the dermatologist operating system", async ({ page }) => {
  const response = await page.goto("/");

  expect(response?.status()).toBe(200);
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "You practice medicine. Ambrosia runs the clinic.", level: 1 })).toBeVisible();
  await expect(page.getByLabel("Current dermatologist")).toContainText("Dr. Maya Chen");
  await expect(page.getByText(/sign in|switch persona|presenter controls/i)).toHaveCount(0);

  await page.getByRole("button", { name: "Resolve 3 stops" }).click();
  const review = page.getByRole("dialog", { name: "Sarah Mitchell" });
  await review.getByRole("button", { name: "Approve & release" }).click();
  await expect(review.getByText("Decision approved and released.")).toBeVisible();
  await review.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("heading", { name: "Needs your judgment · 2" })).toBeVisible();
});

test("keeps the complete clinician workspace connected through canonical routes", async ({ page }) => {
  await page.goto("/");

  const routes = [
    ["Patients", "/patients", "Every patient has a horizon."],
    ["Schedule", "/schedule", "The day is already prepared."],
    ["Inbox", "/messages", "284 conversations are moving."],
    ["Results", "/pathology", "Every result has an owner and an ending."],
    ["Revenue", "/rcm", "$87,420 is moving through 312 care journeys."],
    ["Operations", "/mso", "One intelligence layer. Every patient journey."],
  ] as const;

  for (const [link, path, heading] of routes) {
    await page.getByRole("link", { name: link, exact: true }).click();
    await expect(page).toHaveURL(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
  }

  await page.getByRole("link", { name: "Schedule", exact: true }).click();
  await page.getByRole("link", { name: "Open care agent" }).click();
  await expect(page).toHaveURL("/patients/sarah-mitchell");
  await expect(page.getByRole("heading", { name: "Sarah Mitchell", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Patients", exact: true })).toHaveAttribute("aria-current", "page");
});

test("does not retain compatibility routes", async ({ request }) => {
  for (const route of legacyRoutes) {
    const response = await request.get(route, { maxRedirects: 0 });
    expect(response.status(), route).toBe(404);
    expect(response.headers().location, route).toBeUndefined();
  }
});

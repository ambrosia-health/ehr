import { expect, test } from "@playwright/test";

const legacyRoutes = [
  "/login",
  "/command-center",
  "/patient/start",
  "/presenter",
  "/encounters/sarah-biopsy",
  "/schedule",
  "/messages",
  "/pathology",
  "/rcm",
  "/rcm/denials",
  "/mso",
];

test("opens directly into the dermatologist operating system", async ({ page }) => {
  const response = await page.goto("/");

  expect(response?.status()).toBe(200);
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Good morning, Maya.", level: 1 })).toBeVisible();
  await expect(page.getByLabel("Current dermatologist")).toContainText("Dr. Maya Chen");
  await expect(page.getByText(/sign in|switch persona|presenter controls/i)).toHaveCount(0);

  await expect(page.getByText("Sarah Mitchell", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Clinical decisions", level: 2 })).toBeVisible();
  await expect(page.getByText("312 active journeys")).toHaveCount(0);
  await expect(page.getByText(/Jordan Lee|Natalie Wong|Alex Rivera/)).toHaveCount(0);
});

test("keeps the focused clinician workspace connected through canonical routes", async ({ page }) => {
  await page.goto("/");

  const routes = [
    ["Patients", "/patients", "Patients"],
    ["Practice", "/practice", /Practice (is running|needs review)\./],
  ] as const;

  for (const [link, path, heading] of routes) {
    await page.getByRole("link", { name: link, exact: true }).click();
    await expect(page).toHaveURL(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
  }

  await page.getByRole("link", { name: "Patients", exact: true }).click();
  await page.getByRole("link", { name: "Open Sarah Mitchell", exact: true }).click();
  await expect(page).toHaveURL(/\/patients\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "Sarah Mitchell", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Patients", exact: true })).toHaveAttribute("aria-current", "page");
});

test("keeps the internal learning console outside clinician navigation", async ({ page }) => {
  const response = await page.goto("/internal/learning");

  expect(response?.status()).toBe(200);
  await expect(page.getByText("Ambrosia Learning", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Learning Console access" })).toBeVisible();
  await expect(page.getByLabel("Presenter code")).toHaveAttribute("type", "password");
  await expect(page.getByRole("link", { name: "Today", exact: true })).toHaveCount(0);
});

test("does not retain compatibility routes", async ({ request }) => {
  for (const route of legacyRoutes) {
    const response = await request.get(route, { maxRedirects: 0 });
    expect(response.status(), route).toBe(404);
    expect(response.headers().location, route).toBeUndefined();
  }
});

import { expect, test, type Page } from "@playwright/test";

const liveApiConfigured = ["1", "true"].includes((process.env.E2E_LIVE_API ?? "").toLowerCase()) && Boolean(process.env.PRESENTER_ACCESS_CODE);
const journeyTimeout = Number(process.env.E2E_TIMEOUT_MS ?? 180_000);

if (!Number.isFinite(journeyTimeout) || journeyTimeout < 30_000) {
  throw new Error("E2E_TIMEOUT_MS must be a number of milliseconds greater than or equal to 30000.");
}

async function switchPersona(page: Page, name: string, destination: RegExp) {
  await page.getByLabel("Switch demo persona").click();
  await page.getByRole("menuitem").filter({ hasText: name }).click();
  await expect(page).toHaveURL(destination);
}

async function clickAndAwaitApi(
  page: Page,
  testId: string,
  pathFragment: string,
  method: "PATCH" | "POST" = "POST",
) {
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes(pathFragment) && response.request().method() === method,
  );
  await page.getByTestId(testId).click();
  const response = await responsePromise;
  expect(response.ok(), `${method} ${pathFragment} returned ${response.status()}`).toBe(true);
}

async function runPresenterAction(page: Page, id: string, pathFragment: string) {
  await clickAndAwaitApi(page, `presenter-${id}`, pathFragment);
  await expect(page.getByTestId("presenter-action-receipt")).toBeVisible();
}

async function openPresenterChapter(page: Page, number: number, destination: RegExp) {
  await page.goto("/presenter");
  await expect(page.getByRole("heading", { name: "Presenter console" })).toBeVisible();
  await clickAndAwaitApi(page, `presenter-chapter-${number}`, "/api/auth/switch");
  await expect(page).toHaveURL(destination);
}

async function openConversation(page: Page, patientName: string, subject: string) {
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes("/api/conversations/") && response.url().endsWith("/read") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: `Open conversation with ${patientName}: ${subject}` }).click();
  const response = await responsePromise;
  expect(response.ok(), `POST conversation read returned ${response.status()}`).toBe(true);
}

async function completedClaimEvents(page: Page) {
  const summary = page.getByText(/^\d+ of \d+ payer events complete$/);
  await expect(summary).toBeVisible();
  const completed = Number.parseInt(await summary.innerText(), 10);
  expect(Number.isNaN(completed), "Claim lifecycle summary must begin with its completed-event count").toBe(false);
  return completed;
}

test.describe("Sarah Mitchell live demo journey", () => {
  test.setTimeout(journeyTimeout);
  test.skip(
    !liveApiConfigured && !process.env.CI,
    "Set E2E_LIVE_API=1 and PRESENTER_ACCESS_CODE to run against the live FastAPI stack.",
  );

  test.beforeAll(() => {
    if (!liveApiConfigured) {
      throw new Error(
        "Live E2E is mandatory in CI: set E2E_LIVE_API=1 and PRESENTER_ACCESS_CODE.",
      );
    }
  });

  test("persists the canonical patient, clinical, pathology, messaging, claim, and MSO story", async ({ page }) => {
    const presenterCode = process.env.PRESENTER_ACCESS_CODE;
    if (!presenterCode) throw new Error("PRESENTER_ACCESS_CODE is required.");
    const signedEdit = "E2E verification: patient questions answered and return precautions reviewed.";
    let savedNoteVersion = "";

    await test.step("unlock presenter mode and reset the canonical scenario", async () => {
      await page.goto("/login");
      const ownerPersona = page.getByTestId("persona-owner");
      await expect(async () => {
        await ownerPersona.click();
        await expect(ownerPersona).toHaveAttribute("aria-pressed", "true", { timeout: 1_000 });
      }).toPass({ timeout: 10_000 });
      await page.getByLabel("Presenter access code").fill(presenterCode);
      await clickAndAwaitApi(page, "enter-demo", "/api/auth/demo/session");
      await expect(page).toHaveURL(/\/mso/);
      await page.getByTestId("presenter-rail-toggle").click();
      await clickAndAwaitApi(page, "presenter-reset", "/api/demo/reset");
      await expect(page).toHaveURL(/\/presenter$/);
      await openPresenterChapter(page, 1, /\/patient\/start/);
    });

    await test.step("book Sarah's visit through validated intake", async () => {
      await expect(page.getByRole("heading", { name: "Let’s understand what changed." })).toBeVisible();
      const headings = [
        "What have you noticed?",
        "Help your dermatologist prepare.",
        "Do any urgent warning signs apply?",
      ];
      for (const heading of headings) {
        await page.getByTestId("intake-next").click();
        await expect(page.getByRole("heading", { name: heading })).toBeVisible();
      }
      await page.getByRole("checkbox", { name: "None of these" }).click();
      await page.getByTestId("intake-next").click();
      await expect(page.getByRole("heading", { name: "Add a clear photo of the spot." })).toBeVisible();
      await page.getByTestId("intake-next").click();
      await expect(page.getByRole("heading", { name: "Choose a time that works." })).toBeVisible();
      await page.getByRole("radio").first().click();
      await page.getByTestId("intake-next").click();
      await expect(page.getByRole("heading", { name: "Your coverage is active." })).toBeVisible();
      await page.getByTestId("intake-next").click();
      await expect(page.getByRole("heading", { name: "Review your visit." })).toBeVisible();
      await page.getByRole("checkbox", { name: /consent to evaluation and treatment/i }).click();
      await page.getByRole("checkbox", { name: /acknowledge the privacy notice/i }).click();
      await page.getByRole("checkbox", { name: /consent to clinical photography/i }).click();
      await clickAndAwaitApi(page, "book-appointment", "/api/intake/submissions");
      await expect(page).toHaveURL(/\/patient\/confirmation/);
      await expect(page.getByText("You’re all set, Sarah.")).toBeVisible();
    });

    await test.step("save a versioned note and structured lesion observation", async () => {
      await openPresenterChapter(page, 2, /\/command-center/);
      await expect(page.getByRole("heading", { name: "Good morning, Jordan." })).toBeVisible();
      await page.setViewportSize({ width: 390, height: 844 });
      await page.getByLabel("Open navigation").click();
      const mobileNavigation = page.getByRole("dialog");
      await expect(mobileNavigation).toBeVisible();
      await mobileNavigation.getByRole("link", { name: "Command center" }).click();
      await expect(mobileNavigation).toBeHidden();
      await page.setViewportSize({ width: 1440, height: 1000 });
      await openPresenterChapter(page, 3, /\/encounters\/sarah-biopsy$/);

      const note = page.getByLabel("Assessment and plan");
      await note.fill(`${await note.inputValue()}\n\n${signedEdit}`);
      await clickAndAwaitApi(page, "save-note-draft", "/api/notes/", "PATCH");
      await expect(page.getByTestId("note-draft-receipt")).toBeVisible();
      await expect(page.getByTestId("review-complete")).toBeEnabled();
      savedNoteVersion = await page.getByTestId("note-version").getAttribute("data-version") ?? "";
      expect(Number(savedNoteVersion)).toBeGreaterThan(1);

      await page.getByRole("tab", { name: "Lesion" }).click();
      await page.getByLabel("Length (mm)").fill("7.2");
      await clickAndAwaitApi(page, "save-lesion-observation", "/api/lesions/observations");
      await expect(page.getByTestId("lesion-observation-receipt")).toContainText("Timeline event saved");
      await page.reload();
      await page.getByRole("tab", { name: "Lesion" }).click();
      await expect(page.getByLabel("Length (mm)")).toHaveValue("7.2");
    });

    await test.step("approve the encounter and assert durable downstream IDs", async () => {
      await openPresenterChapter(page, 4, /\/encounters\/sarah-biopsy\/review/);
      await page.getByRole("checkbox", { name: /I reviewed the source transcript/i }).click();
      await clickAndAwaitApi(page, "complete-encounter", "/api/encounters/");
      await expect(page.getByText("Every approved handoff is in motion.")).toBeVisible();
      const receipt = page.getByTestId("encounter-completion-receipt");
      await expect(receipt).toContainText("Note signed");
      await expect(receipt).toContainText("Specimen ordered");
      await expect(receipt).toContainText("Aftercare sent");
      await expect(receipt).toContainText("Claim drafted");

      await page.goto("/encounters/sarah-biopsy");
      const signedNote = page.getByLabel("Assessment and plan");
      await expect(signedNote).toHaveAttribute("readonly", "");
      const signedContent = await signedNote.inputValue();
      expect(signedContent.split(signedEdit)).toHaveLength(2);
      await expect(page.getByTestId("note-version")).toHaveAttribute("data-version", savedNoteVersion);
    });

    await test.step("deliver pathology explicitly, then close the durable result", async () => {
      await openPresenterChapter(page, 5, /\/pathology/);
      await expect(page.getByTestId("pathology-status")).toHaveAttribute("data-status", "pending");
      await page.getByTestId("presenter-rail-toggle").click();
      await runPresenterAction(page, "pathology", "/api/demo/triggers/pathology");
      await page.getByLabel("Collapse presenter rail").click();
      await expect(page.getByTestId("review-pathology")).toBeEnabled();
      await clickAndAwaitApi(page, "review-pathology", "/api/pathology/results/");
      await expect(page.getByTestId("pathology-review-receipt")).toContainText("Review recorded");
      await expect(page.getByTestId("pathology-status")).toHaveAttribute("data-status", "reviewed");
      await expect(page.getByText("Closure complete")).toHaveCount(0);
      const firstReviewedAt = await page.getByTestId("pathology-reviewed-at").getAttribute("datetime");
      expect(firstReviewedAt).toBeTruthy();

      await page.reload();
      await expect(page.getByTestId("pathology-status")).toHaveAttribute("data-status", "reviewed");
      await expect(page.getByTestId("pathology-reviewed-at")).toHaveAttribute("datetime", firstReviewedAt!);
      await expect(page.getByText("Closure complete")).toHaveCount(0);

      await page.getByRole("checkbox", { name: /Approve patient communication/i }).click();
      await expect(page.getByTestId("review-pathology")).toContainText("Notify patient");
      await clickAndAwaitApi(page, "review-pathology", "/api/pathology/results/");
      await expect(page.getByTestId("pathology-status")).toHaveAttribute("data-status", "notified");
      await expect(page.getByText("Closure complete")).toBeVisible();

      await page.reload();
      await expect(page.getByTestId("pathology-status")).toHaveAttribute("data-status", "notified");
      await expect(page.getByTestId("pathology-reviewed-at")).toHaveAttribute("datetime", firstReviewedAt!);
      await expect(page.getByText("Closure complete")).toBeVisible();
      await expect(page.getByTestId("pathology-followup")).toBeEnabled();
      await page.getByTestId("pathology-followup").click();
      await expect(page.getByTestId("review-pathology")).toContainText("Create follow-up");
      await clickAndAwaitApi(page, "review-pathology", "/api/pathology/results/");
      await page.reload();
      await expect(page.getByTestId("pathology-followup")).toBeDisabled();
      await expect(page.getByTestId("pathology-reviewed-at")).toHaveAttribute("datetime", firstReviewedAt!);
    });

    await test.step("route an uncertain patient message, then approve its grounded response", async () => {
      await switchPersona(page, "Sarah Mitchell", /\/patient\/start/);
      await page.goto("/messages");
      await openConversation(page, "Sarah Mitchell", "Shoulder biopsy and aftercare");
      await page.getByLabel("Message your care team").fill(
        "The biopsy site is warmer and redder today, and I am not sure whether it is infected. What should I do?",
      );
      await clickAndAwaitApi(page, "send-message", "/api/conversations/");
      const uncertainReceipt = page.getByTestId("message-receipt");
      await expect(uncertainReceipt).toHaveAttribute("data-triage", "staff_review");
      await expect(uncertainReceipt).toContainText("Routed to staff task");

      await switchPersona(page, "Dr. Maya Chen", /\/command-center/);
      await page.goto("/messages");
      await openConversation(page, "Sarah Mitchell", "Shoulder biopsy and aftercare");
      await expect(page.getByText("Grounded reply ready")).toBeVisible();
      await clickAndAwaitApi(page, "send-message", "/api/conversations/");
      await expect(page.getByTestId("message-receipt")).toHaveAttribute("data-triage", "routine");
    });

    await test.step("advance Sarah's payer lifecycle and persist denial recovery", async () => {
      await openPresenterChapter(page, 6, /\/rcm/);

      await page.goto("/rcm/denials");
      await clickAndAwaitApi(page, "resubmit-claim", "/correct-and-resubmit");
      await expect(page.getByTestId("denial-resubmit-receipt")).toContainText("Corrected claim");

      await page.goto("/rcm");
      await page.getByRole("link", { name: "Open related claim" }).click();
      const before = await completedClaimEvents(page);
      await page.getByRole("link", { name: "Revenue cycle", exact: true }).click();

      await page.getByTestId("presenter-rail-toggle").click();
      await runPresenterAction(page, "advance", "/api/demo/advance-time");
      await runPresenterAction(page, "claim", "/api/demo/triggers/claim-response");
      await runPresenterAction(page, "claim", "/api/demo/triggers/claim-response");
      await page.getByLabel("Collapse presenter rail").click();

      await page.getByRole("link", { name: "Open related claim" }).click();
      const after = await completedClaimEvents(page);
      expect(after).toBeGreaterThan(before);
      await expect(page.getByTestId("claim-status")).toHaveAttribute("data-status", "paid");

      await page.goto("/rcm/denials");
      await page.getByTestId("presenter-rail-toggle").click();
      await runPresenterAction(page, "claim", "/api/demo/triggers/claim-response");
      await runPresenterAction(page, "claim", "/api/demo/triggers/claim-response");
      await runPresenterAction(page, "claim", "/api/demo/triggers/claim-response");
      await page.getByLabel("Collapse presenter rail").click();
      const recovery = page.getByTestId("denial-recovery-status");
      await expect(recovery).toContainText("Revenue recovered");
      await expect(recovery).toHaveAttribute("data-claim-status", "paid");
    });

    await test.step("finish on API-backed owner metrics", async () => {
      await openPresenterChapter(page, 7, /\/mso/);
      await expect(page.getByRole("heading", { name: "Practice performance" })).toBeVisible();
      await expect(page.getByText("Support", { exact: true }).first()).toBeVisible();
    });

    await test.step("end the cookie session and protect browser history", async () => {
      await page.getByLabel("Switch demo persona").click();
      await clickAndAwaitApi(page, "exit-demo", "/api/auth/logout");
      await expect(page).toHaveURL(/\/login$/);
      await page.goBack();
      await expect(page).toHaveURL(/\/login$/);
    });
  });
});

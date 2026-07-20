import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement } from "react";

import type { ProductWorkspace } from "@/components/platform/product-workspace";
import { ProductWorkspaceProvider } from "@/components/platform/product-workspace-provider";

interface WorkspaceFixtureOptions {
  assessmentPlan?: string;
  completed?: boolean;
  staffReview?: boolean;
}

export function createProductWorkspace({
  assessmentPlan = "Favor dysplastic nevus; rule out melanoma. Recommend shave biopsy today after informed consent.",
  completed = false,
  staffReview = false,
}: WorkspaceFixtureOptions = {}): ProductWorkspace {
  return {
    session: { displayName: "Dr. Maya Chen", persona: "provider", roles: ["provider"] },
    organization: { id: "org-1", name: "Ambrosia Dermatology Partners", location: "Midtown · New York", timezone: "America/New_York" },
    scenario: { currentTime: "2026-07-16T13:00:00Z", modelMode: "deterministic_fallback" },
    intake: {
      bookedAppointment: { startsAt: "2026-07-16T18:30:00Z", status: "checked_in" },
      eligibility: { payer: "Blue Horizon PPO", plan: "Preferred PPO", estimatedResponsibility: 85 },
    },
    commandCenter: {
      scheduledVisits: 1,
      completedVisits: completed ? 1 : 0,
      inProgressVisits: completed ? 0 : 1,
      readinessPercent: 100,
      medianSignMinutes: completed ? 8 : null,
      pathologyClosurePercent: 100,
      pathologyDueToday: 0,
      eligibilityVerified: 1,
      summariesPrepared: 1,
      documentationSupportPercent: 100,
    },
    patient: {
      id: "patient-1",
      name: "Sarah Mitchell",
      initials: "SM",
      age: 38,
      pronouns: "she/her",
      mrn: "AM-10482",
      insurance: "Blue Horizon PPO Preferred PPO · Active",
      allergies: ["Adhesive tape — rash"],
      medications: ["Sertraline 50 mg daily"],
      problems: ["Family history of melanoma", "Atypical nevus"],
      recentEvents: [{ id: "event-1", kind: "appointment", occurredAt: "2026-07-16T18:30:00Z", title: "Lesion evaluation", detail: "Checked In" }],
      readiness: 100,
      readinessStatus: "ready",
      lesion: {
        id: "lesion-1",
        label: "Changing pigmented lesion",
        location: "Left Posterior Shoulder",
        dimensions: "7 × 5 mm",
        morphology: "asymmetric papule",
        border: "irregular border",
        pigmentation: "variegated pigmentation",
        symptoms: ["occasional itch", "no bleeding"],
        change: "Widened and darkened over four months",
        firstObserved: "2026-03-12T14:00:00Z",
        overviewImage: { id: "file-1", url: "/images/clinical/sarah-left-posterior-shoulder.png", name: "overview.png", sha256: "a".repeat(64), capturedAt: "2026-07-16T12:00:00Z" },
        dermoscopyImage: { id: "file-2", url: "/images/clinical/sarah-left-posterior-shoulder-dermoscopy.png", name: "dermoscopy.png", sha256: "b".repeat(64), capturedAt: "2026-07-16T12:05:00Z" },
        latestObservation: { assessment: "Changing lesion requires clinician review", comparison: "New irregular pigmentation compared with baseline.", observedAt: "2026-07-16T12:00:00Z" },
      },
    },
    schedule: [{ id: "appointment-1", startsAt: "2026-07-16T18:30:00Z", time: "2:30 PM", patient: "Sarah Mitchell", visit: "Lesion evaluation", provider: "Dr. Maya Chen", readiness: 100, readinessStatus: "ready", flags: ["AI summary"], status: completed ? "Completed" : "Checked In" }],
    queues: [
      { id: "path", label: "Pathology to review", count: 0, detail: "Final results awaiting clinician action", tone: "warning" },
      { id: "notes", label: "Unsigned notes", count: completed ? 0 : 1, detail: "Drafts requiring provider signature", tone: "info" },
      { id: "intake", label: "Missing intake", count: 0, detail: "Across today's visits", tone: "neutral" },
      { id: "messages", label: "Patient messages", count: staffReview ? 1 : 0, detail: "Secure threads awaiting response", tone: "ai" },
      { id: "refills", label: "Refill requests", count: 0, detail: "Protocol-routed requests", tone: "success" },
    ],
    encounter: {
      id: "encounter-1",
      noteId: "note-1",
      status: completed ? "signed" : "draft",
      completionReceipt: completed ? { claimId: "claim-1" } : null,
      note: {
        id: "note-1",
        status: completed ? "signed" : "draft",
        signedAt: completed ? "2026-07-16T13:08:00Z" : null,
        currentVersion: { id: "version-1", number: completed ? 2 : 1, createdAt: "2026-07-16T13:00:00Z", reason: "Ambient transcript draft", contentHash: "c".repeat(64) },
      },
      previsitSummary: "Changing lesion visit ready for review.",
      draftNote: { chiefConcern: "Changing lesion", historyOfPresentIllness: "Changing for four months", focusedExam: "7 × 5 mm asymmetric pigmented papule", assessmentPlan },
      proposals: [
        { id: "proposal-1", category: "Procedure", title: "Perform shave biopsy", detail: "Local anesthesia", required: true, status: completed ? "accepted" : "proposed" },
        { id: "proposal-2", category: "Pathology", title: "Create pathology order", detail: "Routine priority", required: true, status: completed ? "accepted" : "proposed" },
      ],
    },
    pathology: { id: null, status: "pending", diagnosis: "Pending specimen collection and pathology", summary: "Review and complete the encounter to create the specimen and order.", closureDueAt: "2026-07-19T13:00:00Z" },
    conversations: [{ id: "conversation-1", subject: "Changing lesion", patientId: "patient-1", patient: "Sarah Mitchell", unread: staffReview ? 1 : 0, risk: staffReview ? "staff_review" : "routine", messages: [{ id: "message-1", sender: "Sarah Mitchell", sentAt: "2026-07-16T12:30:00Z", body: "Will this leave a big scar?" }] }],
    metrics: [
      { id: "sign", label: "Time to signed note", value: completed ? "8m" : null, score: completed ? 100 : null, supportingCount: completed ? "1 signed" : "0 signed", source: "encounters + encounter_notes" },
      { id: "doc", label: "Documentation time", value: "6m", score: 100, supportingCount: "1 completed visit", source: "encounters + encounter_notes" },
    ],
  };
}

export function renderWithProductWorkspace(ui: ReactElement, workspace = createProductWorkspace(), options?: Omit<RenderOptions, "wrapper">) {
  return render(<ProductWorkspaceProvider initialWorkspace={workspace}>{ui}</ProductWorkspaceProvider>, options);
}

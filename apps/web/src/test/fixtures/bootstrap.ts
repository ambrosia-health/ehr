import type { DemoBootstrap } from "@/lib/api/types";

export const bootstrapFixture = {
  session: { authenticated: true, persona: "patient", presenter: false },
  organization: { id: "org-1", name: "Ambrosia Dermatology", location: "Union Square", timezone: "America/New_York" },
  scenario: { id: "scenario-1", chapter: 1, chapterLabel: "Patient initiation", currentTime: "2026-07-16T09:12:00-04:00", modelMode: "live" },
  personas: [
    { id: "patient", name: "Sarah Mitchell", title: "Patient", initials: "SM" },
    { id: "provider", name: "Dr. Maya Chen", title: "Dermatologist", initials: "MC" },
    { id: "clinical", name: "Jordan Lee", title: "Clinical coordinator", initials: "JL" },
    { id: "biller", name: "Priya Shah", title: "RCM specialist", initials: "PS" },
    { id: "owner", name: "Alex Morgan", title: "MSO owner", initials: "AM" },
  ],
  intake: {
    draft: { reason: "", firstNoticed: "", change: [], symptoms: [], medications: [], allergies: [], personalSkinCancerHistory: "", familySkinCancerHistory: "", pharmacy: "", urgentSigns: [] },
    availableSlots: [
      { id: "11111111-1111-4111-8111-111111111111", startsAt: "2026-07-16T09:00:00-04:00", dayLabel: "Today", dateLabel: "Thu, Jul 16", timeLabel: "9:00 AM", provider: "Dr. Maya Chen", location: "Union Square", providerId: "21111111-1111-4111-8111-111111111111", locationId: "31111111-1111-4111-8111-111111111111" },
      { id: "12222222-2222-4222-8222-222222222222", startsAt: "2026-07-16T09:00:00-04:00", dayLabel: "Today", dateLabel: "Thu, Jul 16", timeLabel: "9:00 AM", provider: "Dr. Imani Okafor", location: "Midtown", providerId: "22222222-2222-4222-8222-222222222222", locationId: "32222222-2222-4222-8222-222222222222" },
    ],
    bookedAppointment: null,
    triage: { status: "routine", taskId: null, notificationId: null, readinessStatus: "unknown" },
    eligibility: { payer: "Blue Horizon", plan: "Preferred PPO", status: "Active", network: "In network", memberId: "M-100", specialistCopay: 50, deductibleRemaining: 240, estimatedResponsibility: 86, checkedAt: "2026-07-16T08:53:00-04:00" },
    appointmentAddress: "41 East 17th Street",
    preparation: ["Bring a photo ID."],
  },
  patient: {
    id: "patient-1", name: "Sarah Mitchell", initials: "SM", dob: "1988-04-12", age: 38, pronouns: "she/her", phone: "555-0100", email: "sarah@example.test", mrn: "MRN-1", pharmacy: "Hudson Community", insurance: "Blue Horizon · Active", allergies: ["Adhesive tape"], medications: ["Sertraline"], problems: ["Family history of melanoma"], readiness: 100, readinessStatus: "ready",
    lesion: { id: "lesion-1", label: "Changing lesion", status: "biopsy_recommended", location: "Left posterior shoulder", dimensions: "7 × 5 mm", morphology: "Asymmetric macule", border: "Irregular", pigmentation: "Variegated", symptoms: ["Itching"], change: "Darkened", firstObserved: "2026-03-08", latestObservation: { id: "observation-1", site: "Left posterior shoulder", view: "posterior", lengthMm: 7, widthMm: 5, morphology: "Asymmetric macule", border: "Irregular, focally notched", pigmentation: "Variegated tan–dark brown", changeOverTime: "Darkened and widened over approximately 4 months", symptoms: ["Occasional itch", "no bleeding", "no pain"], assessment: "Changing pigmented lesion", comparison: "Patient reports change from personal photographs", source: "clinician", observedAt: "2026-07-16T09:10:00-04:00" }, overviewImage: { id: "file-1", url: "/images/clinical/sarah-left-posterior-shoulder.png", name: "sarah-left-posterior-shoulder.png", size: 2838119, type: "image/png", sha256: "69c0f5c4", capturedAt: "2026-07-13T10:00:00-04:00" }, dermoscopyImage: { id: "file-2", url: "/images/clinical/sarah-left-posterior-shoulder-dermoscopy.png", name: "dermoscopy.png", size: 1000, type: "image/png", sha256: "abc", capturedAt: "2026-07-16T09:10:00-04:00" } },
  },
  encounter: {
    id: "encounter-1", noteId: "note-1", status: "draft", aiProvenance: { aiRunId: "ai-run-1", capability: "ambient_note", promptVersion: "ambient-note-v1", provider: "local", model: "deterministic", fallbackUsed: true, schemaValid: true }, completionReceipt: null, note: { id: "note-1", status: "draft", currentVersion: { id: "version-1", number: 1, createdAt: "2026-07-16T09:12:00-04:00", reason: "Initial ambient draft", contentHash: "sha256:fixture" }, author: { id: "provider-1", name: "Dr. Maya Chen" }, signedAt: null, consent: { id: "consent-1", status: "active", version: "2026-01", acceptedAt: "2026-07-16T08:45:00-04:00" } }, previsitSummary: "Changing lesion with family history.", draftNote: { chiefConcern: "Changing mole", historyOfPresentIllness: "Four months of change.", focusedExam: "Asymmetric macule.", assessmentPlan: "Biopsy proposed." }, transcript: [], timeline: [],
    proposals: [
      { id: "a1111111-1111-4111-8111-111111111111", category: "Documentation", title: "Sign note", detail: "Sign structured note.", required: true },
      { id: "a2222222-2222-4222-8222-222222222222", category: "Safety", title: "Create closure task", detail: "Track pathology.", required: true },
      { id: "a3333333-3333-4333-8333-333333333333", category: "Patient communication", title: "Send aftercare", detail: "Approved instructions.", required: false },
    ],
  },
  pathology: { id: "result-1", accession: "ACC-1", status: "received", diagnosis: "Dysplastic nevus", summary: "No melanoma.", receivedAt: "2026-07-21T08:42:00-04:00", reviewedAt: null, notifiedAt: null, closureDueAt: "2026-07-22T17:00:00-04:00", priority: "routine", aiProvenance: { aiRunId: "ai-run-2", capability: "pathology_summary", promptVersion: "pathology-summary-v1", provider: "local", model: "deterministic", fallbackUsed: true, schemaValid: true }, patientMessageDraft: null, followup: null, links: [] },
  conversations: [], claims: [], financialContext: null, metrics: [], health: [], schedule: [], queues: [],
  commandCenter: { scheduledVisits: 1, completedVisits: 0, inProgressVisits: 0, readinessPercent: 92, medianSignMinutes: 24, signMinutesImprovement: 31, pathologyClosurePercent: 99, pathologyDueToday: 0, eligibilityVerified: 1, summariesPrepared: 1, summaryMinutesSaved: 4, documentationSupportPercent: 96 },
  triggerIds: null,
} as unknown as DemoBootstrap;

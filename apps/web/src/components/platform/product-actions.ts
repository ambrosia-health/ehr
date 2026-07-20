import { apiRequest } from "@/lib/api/client";

import type { ProductWorkspace } from "./product-workspace";

export async function completeEncounter(workspace: ProductWorkspace) {
  const version = workspace.encounter.note.currentVersion;
  return apiRequest(`/api/encounters/${workspace.encounter.id}/complete`, {
    method: "POST",
    body: {
      proposedActionIds: workspace.encounter.proposals.map((proposal) => proposal.id),
      attest: true,
      signNote: true,
      attestation: "Reviewed source records and approved all prepared actions.",
      expectedNoteVersion: version.number,
      expectedNoteHash: version.contentHash,
    },
  });
}

export async function updateAssessmentPlan(workspace: ProductWorkspace, assessmentPlan: string) {
  const draft = workspace.encounter.draftNote;
  return apiRequest(`/api/notes/${workspace.encounter.note.id}`, {
    method: "PATCH",
    body: {
      content: [
        `Chief concern: ${draft.chiefConcern}`,
        `History of present illness: ${draft.historyOfPresentIllness}`,
        `Focused exam: ${draft.focusedExam}`,
        `Assessment and plan: ${assessmentPlan}`,
      ].join("\n\n"),
      structuredContent: {
        subjective: draft.historyOfPresentIllness,
        objective: draft.focusedExam,
        assessmentPlan,
      },
      reason: "Clinician edited the prepared assessment and plan",
    },
  });
}

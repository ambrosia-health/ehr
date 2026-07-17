// Synthetic presentation fixtures. These values are not loaded from Modal or persisted to Neon.

export type JourneyStatus = "complete" | "moving" | "waiting" | "human" | "risk";

export interface PatientJourney {
  id: string;
  initials: string;
  name: string;
  age: number;
  pronouns: string;
  mrn: string;
  concern: string;
  goal: string;
  state: "Needs clinician" | "Advancing" | "Waiting external" | "Waiting patient" | "At risk";
  next: string;
  lastEvent: string;
}

export interface AttentionItem {
  id: string;
  initials: string;
  patient: string;
  episode: string;
  reason: string;
  recommendation: string;
  due: string;
  release: string;
  confidence?: number;
  domain: "Clinical" | "Communication" | "Revenue";
  severity: "human" | "risk";
}

export const patientJourneys: PatientJourney[] = [
  {
    id: "sarah-mitchell",
    initials: "SM",
    name: "Sarah Mitchell",
    age: 38,
    pronouns: "she/her",
    mrn: "AM-10482",
    concern: "Changing lesion",
    goal: "Resolve changing lesion through safe pathology closure",
    state: "Needs clinician",
    next: "Review biopsy plan · now",
    lastEvent: "Previsit synthesis completed · 8:09 AM",
  },
  {
    id: "alex-rivera",
    initials: "AR",
    name: "Alex Rivera",
    age: 29,
    pronouns: "he/him",
    mrn: "AM-99112",
    concern: "Acne follow-up",
    goal: "Achieve clear, stable skin and prevent flares",
    state: "Advancing",
    next: "Patient photo check · tomorrow",
    lastEvent: "Medication plan released · 9:29 AM",
  },
  {
    id: "natalie-wong",
    initials: "NW",
    name: "Natalie Wong",
    age: 33,
    pronouns: "she/her",
    mrn: "AM-55321",
    concern: "Psoriasis",
    goal: "Control plaques and monitor biologic therapy",
    state: "Waiting external",
    next: "CBC/CMP expected · Jul 20",
    lastEvent: "Lab order reconciled · 11:05 AM",
  },
  {
    id: "jordan-lee",
    initials: "JL",
    name: "Jordan Lee",
    age: 45,
    pronouns: "he/him",
    mrn: "AM-77211",
    concern: "Post-Mohs left cheek",
    goal: "Complete closure and monitor healing",
    state: "Waiting patient",
    next: "Wound photo · tomorrow",
    lastEvent: "Wound instructions delivered · yesterday",
  },
  {
    id: "benjamin-carter",
    initials: "BC",
    name: "Benjamin Carter",
    age: 52,
    pronouns: "he/him",
    mrn: "AM-22918",
    concern: "Annual mole check",
    goal: "Complete surveillance and close preventive care",
    state: "Advancing",
    next: "Routine surveillance · Jan 2027",
    lastEvent: "Payment reconciled · 11:52 AM",
  },
  {
    id: "emily-lopez",
    initials: "EL",
    name: "Emily Lopez",
    age: 41,
    pronouns: "she/her",
    mrn: "AM-84720",
    concern: "Rash evaluation",
    goal: "Identify trigger and resolve recurrent dermatitis",
    state: "Advancing",
    next: "Treatment response check · Jul 23",
    lastEvent: "Aftercare delivered · 12:42 PM",
  },
];

export const attentionItems: AttentionItem[] = [
  {
    id: "sarah-biopsy",
    initials: "SM",
    patient: "Sarah Mitchell",
    episode: "Changing lesion",
    reason: "The lesion widened and darkened over four months. Ambrosia cannot choose an invasive plan.",
    recommendation: "Shave biopsy of the left posterior shoulder",
    due: "Before 8:30 AM visit",
    release: "Procedure plan, pathology order, aftercare, specimen monitor, estimate, and claim draft",
    confidence: 91,
    domain: "Clinical",
    severity: "human",
  },
  {
    id: "jordan-pathology",
    initials: "JL",
    patient: "Jordan Lee",
    episode: "Pathology follow-up",
    reason: "Final pathology is nodular basal cell carcinoma. Result explanation requires clinician disposition.",
    recommendation: "Confirm Mohs referral and patient explanation",
    due: "SLA in 2h 18m",
    release: "Referral, patient message, scheduling outreach, claim update, and closure monitor",
    confidence: 96,
    domain: "Clinical",
    severity: "human",
  },
  {
    id: "natalie-symptoms",
    initials: "NW",
    patient: "Natalie Wong",
    episode: "Biologic monitoring",
    reason: "Natalie reported new joint pain. Safety language is outside the routine psoriasis check-in policy.",
    recommendation: "Review symptoms and choose triage disposition",
    due: "Patient waiting 47m",
    release: "Acknowledgment, clinical task, lab coordination, and treatment-monitor update",
    confidence: 88,
    domain: "Communication",
    severity: "risk",
  },
];

export const stateTone = {
  "Needs clinician": "human",
  Advancing: "moving",
  "Waiting external": "waiting",
  "Waiting patient": "waiting",
  "At risk": "risk",
} as const satisfies Record<PatientJourney["state"], JourneyStatus>;

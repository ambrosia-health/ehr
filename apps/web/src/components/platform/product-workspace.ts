export interface ProductWorkspace {
  session: {
    displayName: string;
    persona: string;
    roles: string[];
  };
  organization: {
    id: string;
    name: string;
    location: string;
    timezone: string;
  };
  scenario: {
    currentTime: string;
    modelMode: string;
  };
  intake: {
    bookedAppointment: {
      startsAt: string;
      status: string;
    } | null;
    eligibility: {
      payer: string;
      plan: string;
      estimatedResponsibility: number;
    };
  } | null;
  commandCenter: {
    scheduledVisits: number;
    completedVisits: number;
    inProgressVisits: number;
    readinessPercent: number;
    medianSignMinutes: number | null;
    pathologyClosurePercent: number;
    pathologyDueToday: number;
    eligibilityVerified: number;
    summariesPrepared: number;
    documentationSupportPercent: number;
  };
  patient: {
    id: string;
    name: string;
    initials: string;
    age: number;
    pronouns: string;
    mrn: string;
    insurance: string;
    allergies: string[];
    medications: string[];
    problems: string[];
    recentEvents: Array<{
      id: string;
      kind: string;
      occurredAt: string;
      title: string;
      detail: string;
    }>;
    readiness: number;
    readinessStatus: string;
    lesion: {
      id: string;
      label: string;
      location: string;
      dimensions: string;
      morphology: string;
      border: string;
      pigmentation: string;
      symptoms: string[];
      change: string;
      firstObserved: string;
      overviewImage: ProductImage;
      dermoscopyImage: ProductImage;
      latestObservation: {
        assessment: string | null;
        comparison: string | null;
        observedAt: string;
      };
    };
  };
  schedule: Array<{
    id: string;
    startsAt: string;
    time: string;
    patient: string;
    visit: string;
    provider: string;
    readiness: number;
    readinessStatus: string;
    flags: string[];
    status: string;
  }>;
  queues: Array<{
    id: string;
    label: string;
    count: number;
    detail: string;
    tone: string;
  }>;
  encounter: {
    id: string;
    noteId: string;
    status: string;
    completionReceipt: Record<string, unknown> | null;
    note: {
      id: string;
      status: string;
      signedAt: string | null;
      currentVersion: {
        id: string;
        number: number;
        createdAt: string;
        reason: string;
        contentHash: string;
      };
    };
    previsitSummary: string;
    draftNote: {
      chiefConcern: string;
      historyOfPresentIllness: string;
      focusedExam: string;
      assessmentPlan: string;
    };
    proposals: Array<{
      id: string;
      category: string;
      title: string;
      detail: string;
      required: boolean;
      status: string;
    }>;
  };
  pathology: {
    id: string | null;
    status: string;
    diagnosis: string;
    summary: string;
    closureDueAt: string;
  };
  conversations: Array<{
    id: string;
    subject: string;
    patientId: string;
    patient: string;
    unread: number;
    risk: string;
    messages: Array<{
      id: string;
      sender: string;
      sentAt: string;
      body: string;
    }>;
  }>;
  metrics: Array<{
    id: string;
    label: string;
    value: string | null;
    score: number | null;
    supportingCount: string;
    source: string;
  }>;
}

interface ProductImage {
  id: string;
  url: string;
  name: string;
  sha256: string;
  capturedAt: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isProductWorkspace(value: unknown): value is ProductWorkspace {
  if (!isRecord(value)) return false;
  const patient = value.patient;
  const encounter = value.encounter;
  const commandCenter = value.commandCenter;
  const session = value.session;

  return isRecord(session)
    && typeof session.displayName === "string"
    && Array.isArray(session.roles)
    && isRecord(value.organization)
    && isRecord(patient)
    && typeof patient.id === "string"
    && isRecord(patient.lesion)
    && isRecord(encounter)
    && typeof encounter.id === "string"
    && isRecord(encounter.note)
    && Array.isArray(encounter.proposals)
    && isRecord(commandCenter)
    && Array.isArray(value.schedule)
    && Array.isArray(value.queues)
    && Array.isArray(value.conversations)
    && Array.isArray(value.metrics);
}

export function clinicianFirstName(workspace: ProductWorkspace) {
  const withoutTitle = workspace.session.displayName.replace(/^Dr\.\s+/i, "").trim();
  return withoutTitle.split(/\s+/)[0] || workspace.session.displayName;
}

export function clinicianInitials(workspace: ProductWorkspace) {
  return workspace.session.displayName
    .replace(/^Dr\.\s+/i, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function locationName(workspace: ProductWorkspace) {
  return workspace.organization.location.split("·")[0]?.trim() || workspace.organization.name;
}

export function formatWorkspaceDate(value: string, workspace: ProductWorkspace, options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat("en-US", { timeZone: workspace.organization.timezone, ...options }).format(new Date(value));
}

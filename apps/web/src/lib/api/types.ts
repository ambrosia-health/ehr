export type Persona = "patient" | "provider" | "clinical" | "biller" | "owner";

export type ApiMode = "loading" | "live" | "error";

export type StatusTone =
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "danger"
  | "ai";

export interface BookedAppointment {
  id: string;
  slotId: string;
  providerId: string;
  provider: string;
  locationId: string;
  location: string;
  startsAt: string;
  status: string;
}

export interface IntakeTriageReceipt {
  status: "routine" | "staff_review";
  taskId: string | null;
  notificationId: string | null;
  readinessStatus: "ready" | "needs_review" | "unknown";
}

export interface AiProvenance {
  aiRunId: string;
  capability: string;
  promptVersion: string;
  provider: string;
  model: string;
  fallbackUsed: boolean;
  schemaValid: boolean;
}

export interface DemoBootstrap {
  session: {
    authenticated: boolean;
    persona: Persona;
    presenter: boolean;
  };
  organization: {
    id: string;
    name: string;
    location: string;
    timezone: string;
  };
  scenario: {
    id: string;
    chapter: number;
    chapterLabel: string;
    currentTime: string;
    modelMode: "live" | "deterministic_fallback";
  };
  personas: Array<{
    id: Persona;
    name: string;
    title: string;
    initials: string;
  }>;
  intake: {
    draft: {
      reason: string;
      firstNoticed: string;
      change: string[];
      symptoms: string[];
      medications: string[];
      allergies: string[];
      personalSkinCancerHistory: string;
      familySkinCancerHistory: string;
      pharmacy: string;
      urgentSigns: string[];
    };
    availableSlots: Array<{
      id: string;
      startsAt: string;
      dayLabel: string;
      dateLabel: string;
      timeLabel: string;
      provider: string;
      location: string;
      providerId: string;
      locationId: string;
    }>;
    bookedAppointment: BookedAppointment | null;
    triage: IntakeTriageReceipt;
    eligibility: {
      payer: string;
      plan: string;
      status: string;
      network: string;
      memberId: string;
      specialistCopay: number;
      deductibleRemaining: number;
      estimatedResponsibility: number;
      checkedAt: string;
    };
    appointmentAddress: string;
    preparation: string[];
  } | null;
  commandCenter: {
    scheduledVisits: number;
    completedVisits: number;
    inProgressVisits: number;
    readinessPercent: number;
    medianSignMinutes: number;
    signMinutesImprovement: number;
    pathologyClosurePercent: number;
    pathologyDueToday: number;
    eligibilityVerified: number;
    summariesPrepared: number;
    summaryMinutesSaved: number;
    documentationSupportPercent: number;
  } | null;
  patient: {
    id: string;
    name: string;
    initials: string;
    dob: string;
    age: number;
    pronouns: string;
    phone: string;
    email: string;
    mrn: string;
    pharmacy: string;
    insurance: string;
    allergies: string[];
    medications: string[];
    problems: string[];
    readiness: number;
    readinessStatus: string;
    lesion: {
      id: string;
      label: string;
      status: string;
      location: string;
      dimensions: string;
      morphology: string;
      border: string;
      pigmentation: string;
      symptoms: string[];
      change: string;
      overviewImage: {
        id: string;
        url: string;
        name: string;
        size: number;
        type: string;
        sha256: string;
        capturedAt: string;
      };
      dermoscopyImage: {
        id: string;
        url: string;
        name: string;
        size: number;
        type: string;
        sha256: string;
        capturedAt: string;
      };
      firstObserved: string;
      latestObservation: {
        id: string;
        site: string;
        view: string;
        lengthMm: number;
        widthMm: number;
        morphology: string;
        border: string;
        pigmentation: string;
        changeOverTime: string;
        symptoms: string[];
        assessment: string | null;
        comparison: string | null;
        source: string;
        observedAt: string;
      };
    };
  } | null;
  schedule: Array<{
    id: string;
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
    tone: StatusTone;
    href: string;
  }>;
  encounter: {
    id: string;
    noteId: string;
    status: "draft" | "signed" | "amended";
    aiProvenance: AiProvenance;
    completionReceipt: {
      status: "completed";
      signedAt: string;
      noteId: string;
      consentId: string;
      procedureId: string;
      specimenId: string;
      orderId: string;
      claimId: string;
      messageId: string;
      closureTaskId: string;
    } | null;
    note: {
      id: string;
      status: "draft" | "signed" | "amended";
      currentVersion: {
        id: string;
        number: number;
        createdAt: string;
        reason: string;
        contentHash: string;
      };
      author: { id: string; name: string };
      signedAt: string | null;
      consent: {
        id: string;
        status: "active" | "revoked";
        version: string;
        acceptedAt: string;
      };
    };
    previsitSummary: string;
    draftNote: {
      chiefConcern: string;
      historyOfPresentIllness: string;
      focusedExam: string;
      assessmentPlan: string;
    };
    transcript: Array<{ time: string; speaker: string; text: string }>;
    timeline: Array<{ date: string; title: string; detail: string; tone: StatusTone }>;
    proposals: Array<{
      id: string;
      category: string;
      title: string;
      detail: string;
      required: boolean;
    }>;
  } | null;
  pathology: {
    id: string | null;
    accession: string;
    status: "pending" | "received" | "reviewed" | "notified";
    diagnosis: string;
    summary: string;
    receivedAt: string;
    reviewedAt: string | null;
    notifiedAt: string | null;
    closureDueAt: string;
    priority: "routine" | "high";
    aiProvenance: AiProvenance | null;
    patientMessageDraft: {
      id: string;
      body: string;
      status: string;
      createdAt: string;
      aiProvenance: AiProvenance | null;
    } | null;
    followup: {
      id: string;
      status: string;
      title: string;
      dueAt: string;
      completedAt: string | null;
    } | null;
    links: Array<{
      kind: "patient" | "clinician" | "lesion" | "image" | "procedure" | "specimen" | "order" | "result";
      id: string;
      label: string;
    }>;
  } | null;
  conversations: Array<{
    id: string;
    subject: string;
    patient: string;
    unread: number;
    risk: "routine" | "staff_review";
    messages: Array<{
      id: string;
      sender: string;
      sentAt: string;
      body: string;
      aiDraft?: boolean;
      status?: string;
    }>;
  }>;
  claims: Array<{
    id: string;
    claimNumber: string;
    patient: string;
    payer: string;
    amount: number;
    allowed: number;
    paid: number;
    remainingBalance: number;
    patientResponsibility: number;
    status: "draft" | "validated" | "submitted" | "accepted" | "adjudicated" | "paid" | "denied";
    codes: string[];
    lines: Array<{
      id: string;
      lineNumber: number;
      procedureCode: string;
      diagnosisCodes: string[];
      units: number;
      charge: number;
      allowed: number;
      paid: number;
    }>;
    payments: Array<{
      id: string;
      source: string;
      amount: number;
      method: string | null;
      reference: string | null;
      status: string;
      receivedAt: string;
    }>;
    balance: {
      currentBalance: number;
      status: string;
      lastStatementAt: string | null;
      lastPaymentAt: string | null;
    } | null;
    financialContext: {
      eligibility: {
        id: string;
        status: string;
        checkedAt: string;
        network: string | null;
        copay: number;
        deductibleRemaining: number;
      } | null;
      estimate: {
        id: string;
        status: string;
        totalCharge: number;
        expectedPlanPayment: number;
        patientResponsibility: number;
      } | null;
    };
    provenance: {
      source: string;
      latestEventId: string | null;
      aiProvenance: AiProvenance | null;
    };
    events: Array<{ label: string; at: string; complete: boolean }>;
    denial?: {
      id: string;
      status: string;
      code: string;
      reason: string;
      recommendation: string;
      recommendationSource: "rules_based";
      aiProvenance: AiProvenance | null;
      recoverable: number;
      appealDraft: string;
      assignedTaskId: string;
      recovery: {
        appealId: string;
        status: string;
        outcome: string | null;
        recoveredAmount: number;
        submittedAt: string | null;
      } | null;
    };
  }>;
  financialContext: {
    source: string;
    coverage: {
      id: string;
      payer: string;
      plan: string;
      memberId: string;
      status: string;
    };
    eligibility: {
      id: string;
      status: string;
      network: string | null;
      checkedAt: string;
      copay: number;
      deductibleRemaining: number;
    };
    estimate: {
      id: string;
      status: string;
      totalCharge: number;
      expectedPlanPayment: number;
      patientResponsibility: number;
    };
  } | null;
  metrics: Array<{
    id: string;
    label: string;
    value: string | null;
    change: string;
    target: string;
    score: number | null;
    tone: StatusTone;
    supportingCount: string;
    assumption: string;
    source: string;
  }>;
  health: Array<{
    id: string;
    service: string;
    status: "healthy" | "degraded" | "unavailable";
    latency: string;
  }>;
  triggerIds: {
    patientId: string;
    encounterId: string;
    lesionId: string;
    claimId: string | null;
    pathologyResultId: string | null;
  } | null;
}

export interface IntakeSubmission {
  reason: string;
  firstNoticed: string;
  change: string[];
  symptoms: string[];
  urgentSigns: string[];
  image: {
    fileId: string;
    sha256: string;
    synthetic: true;
  };
  appointmentSlot: string;
  insurancePayer: string;
  insuranceMemberId: string;
  medications: string[];
  allergies: string[];
  personalSkinCancerHistory: string;
  familySkinCancerHistory: string;
  pharmacy: string;
  consents: {
    treatment: boolean;
    privacy: boolean;
    photography: boolean;
  };
}

export interface DemoActionResult {
  mode: "live";
  message: string;
  at: string;
}

export interface LearningOverview {
  episodeCount: number;
  activeEpisodeCount: number;
  environmentRunCount: number;
  activeEnvironmentRunCount: number;
  aiRunCount: number;
  failedAiRunCount: number;
  datasetReleaseCount: number;
  hardViolationCount: number;
}

export interface EpisodeDefinition {
  id: string;
  slug: string;
  version: number;
  name: string;
  description: string;
  episodeType: string;
  maxSteps: number;
  maxDurationSeconds: number;
  actionTypes: string[];
  rewardComponents: string[];
  releasedAt: string | null;
}

export interface EpisodeSummary {
  id: string;
  episodeKey: string;
  definition: string;
  sourceKind: string;
  status: string;
  startedAt: string;
  endedAt: string | null;
  decisionCount: number | null;
  outcomeCount: number | null;
}

export type ModelIdentity =
  | string
  | {
      provider?: string | null;
      model?: string | null;
    }
  | null;

export interface RunSummary {
  id: string;
  status: string;
  mode: string;
  actorRole: string;
  seed: number;
  sequence: number;
  model: ModelIdentity;
  fallbackUsed: boolean | null;
  totalReward: Record<string, number>;
  hardViolationCount: number;
  maxSteps: number | null;
  startedAt: string;
  endedAt: string | null;
  terminationReason?: string | null;
}

export interface AiRunSummary {
  id: string;
  capability: string;
  provider: string;
  model: string;
  status: string;
  fallbackUsed: boolean;
  latencyMs: number | null;
  startedAt: string;
}

export interface DatasetManifest {
  id: string;
  name: string;
  version: number;
  status: string;
  classification: string;
  containsPhi: boolean | null;
  purpose: string[];
  prohibitedUses: string[];
  schemaVersion: string;
  rowCount: number;
  hash: string;
  releasedAt: string | null;
}

export interface LearningConsoleBootstrap {
  overview: LearningOverview;
  episodeDefinitions: EpisodeDefinition[];
  episodes: EpisodeSummary[];
  runs: RunSummary[];
  aiRuns: AiRunSummary[];
  datasets: DatasetManifest[];
}

export interface ObservationResource {
  resourceType?: string;
  resourceIdentityHash?: string;
  resourceVersion?: string | number;
  contentHash?: string;
  sensitivity?: string;
}

export interface TrajectoryOutcome {
  type: string;
  value: unknown;
  provenanceKind: string;
  observedAt: string;
}

export interface TrajectoryStep {
  sequence: number;
  decisionType: string;
  openedAt: string;
  observation: {
    asOfAt: string;
    manifestHash: string;
    syntheticSnapshot: Record<string, unknown> | null;
    resources: ObservationResource[];
  };
  availableActions: string[];
  action: {
    type: string;
    status: string;
    actorKind: string;
    aiRunId: string | null;
  } | null;
  outcomes: TrajectoryOutcome[];
  event: {
    type: string;
    payloadHash: string;
  } | null;
}

export interface EpisodeTrajectory {
  episode: EpisodeSummary;
  steps: TrajectoryStep[];
  nextOffset: number | null;
  evidenceTruncated: boolean;
}

export interface RunHistoryStep {
  sequence: number;
  actionType: string;
  actionStatus: string;
  supportKind: string;
  terminated: boolean;
  terminationReason: string | null;
  reward: Record<string, number>;
  hardViolations: string[];
  stateBeforeHash: string | null;
  stateAfterHash: string | null;
  observationManifestHash: string | null;
  model: {
    provider: string;
    model: string;
    fallbackUsed: boolean;
    latencyMs: number | null;
  } | null;
}

export interface RunHistory {
  run: RunSummary;
  steps: RunHistoryStep[];
  nextAfterStep: number | null;
}

export interface EnvironmentRunView {
  run: {
    id: string;
    status: string;
    sequence: number;
  };
}

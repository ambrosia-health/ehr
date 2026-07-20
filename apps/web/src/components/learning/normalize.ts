import type {
  AiRunSummary,
  DatasetManifest,
  EnvironmentRunView,
  EpisodeDefinition,
  EpisodeSummary,
  EpisodeTrajectory,
  LearningConsoleBootstrap,
  LearningOverview,
  ModelIdentity,
  ObservationResource,
  RunHistory,
  RunSummary,
  TrajectoryOutcome,
} from "@/components/learning/types";

type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value as UnknownRecord : {};
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function field(source: UnknownRecord, camel: string, snake = camel): unknown {
  return source[camel] ?? source[snake];
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : value === null || value === undefined ? fallback : String(value);
}

function number(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function boolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function nullableText(value: unknown): string | null {
  return value === null || value === undefined ? null : text(value);
}

function nullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function numericRecord(value: unknown): Record<string, number> {
  return Object.fromEntries(
    Object.entries(record(value)).flatMap(([key, nested]) => typeof nested === "number" && Number.isFinite(nested) ? [[key, nested]] : []),
  );
}

function normalizeDefinition(value: unknown): EpisodeDefinition {
  const source = record(value);
  return {
    id: text(field(source, "id")),
    slug: text(field(source, "slug"), "episode"),
    version: number(field(source, "version"), 1),
    name: text(field(source, "name"), "Learning episode"),
    description: text(field(source, "description")),
    episodeType: text(field(source, "episodeType", "episode_type"), "healthcare_operations"),
    maxSteps: number(field(source, "maxSteps", "max_steps"), 100),
    maxDurationSeconds: number(field(source, "maxDurationSeconds", "max_duration_seconds"), 0),
    actionTypes: list(field(source, "actionTypes", "action_types")).map((item) => text(item)).filter(Boolean),
    rewardComponents: list(field(source, "rewardComponents", "reward_components")).map((item) => text(item)).filter(Boolean),
    releasedAt: nullableText(field(source, "releasedAt", "released_at")),
  };
}

function normalizeEpisode(value: unknown): EpisodeSummary {
  const source = record(value);
  const definition = normalizeDefinition(field(source, "definition"));
  const id = text(field(source, "id"));
  const seed = field(source, "seed");
  return {
    id,
    episodeKey: text(field(source, "episodeKey", "episode_key"), `${definition.name}${typeof seed === "number" ? ` · seed ${seed}` : ` · ${id.slice(0, 8)}`}`),
    definition: `${definition.name} · v${definition.version}`,
    sourceKind: text(field(source, "sourceKind", "source_kind"), "unknown"),
    status: text(field(source, "status"), "unknown"),
    startedAt: text(field(source, "startedAt", "started_at")),
    endedAt: nullableText(field(source, "endedAt", "ended_at")),
    decisionCount: field(source, "decisionCount", "decision_count") === undefined ? null : number(field(source, "decisionCount", "decision_count")),
    outcomeCount: field(source, "outcomeCount", "outcome_count") === undefined ? null : number(field(source, "outcomeCount", "outcome_count")),
  };
}

function normalizeModel(value: unknown): ModelIdentity {
  if (typeof value === "string") return value;
  const source = record(value);
  if (!Object.keys(source).length) return null;
  return { provider: nullableText(field(source, "provider")), model: nullableText(field(source, "model")) };
}

function normalizeRun(value: unknown): RunSummary {
  const source = record(value);
  const configuration = record(field(source, "configuration"));
  return {
    id: text(field(source, "id")),
    status: text(field(source, "status"), "unknown"),
    mode: text(field(source, "mode"), "simulation"),
    actorRole: text(field(configuration, "actorRole", "actor_role"), text(field(source, "agentKind", "agent_kind"), "environment_agent")),
    seed: number(field(source, "seed")),
    sequence: number(field(source, "sequence"), number(field(source, "currentStep", "current_step"))),
    model: normalizeModel(field(source, "model")) ?? nullableText(field(source, "agentModel", "agent_model")),
    fallbackUsed: typeof field(source, "fallbackUsed", "fallback_used") === "boolean"
      ? boolean(field(source, "fallbackUsed", "fallback_used"))
      : null,
    totalReward: numericRecord(field(source, "totalReward", "total_reward")),
    hardViolationCount: number(field(source, "hardViolationCount", "hard_violation_count")),
    maxSteps: field(configuration, "maxSteps", "max_steps") === undefined
      ? null
      : number(field(configuration, "maxSteps", "max_steps")),
    startedAt: text(field(source, "startedAt", "started_at")),
    endedAt: nullableText(field(source, "endedAt", "ended_at")),
    terminationReason: nullableText(field(source, "terminationReason", "termination_reason")),
  };
}

function normalizeAiRun(value: unknown): AiRunSummary {
  const source = record(value);
  return {
    id: text(field(source, "id")),
    capability: text(field(source, "capability"), "unknown"),
    provider: text(field(source, "provider"), "unknown"),
    model: text(field(source, "model"), "unknown"),
    status: text(field(source, "status"), "unknown"),
    fallbackUsed: boolean(field(source, "fallbackUsed", "fallback_used")),
    latencyMs: field(source, "latencyMs", "latency_ms") === null ? null : number(field(source, "latencyMs", "latency_ms")),
    startedAt: text(field(source, "startedAt", "started_at")),
  };
}

function normalizeDataset(value: unknown): DatasetManifest {
  const source = record(value);
  const classification = text(field(source, "classification"), "governed");
  const explicitPhi = field(source, "containsPhi", "contains_phi");
  return {
    id: text(field(source, "id")),
    name: text(field(source, "name"), "Dataset release"),
    version: number(field(source, "version"), 1),
    status: text(field(source, "status"), "unknown"),
    classification,
    containsPhi: typeof explicitPhi === "boolean" ? explicitPhi : classification === "synthetic" ? false : null,
    purpose: list(field(source, "purpose") ?? field(source, "intendedUses", "intended_uses")).map((item) => text(item)).filter(Boolean),
    prohibitedUses: list(field(source, "prohibitedUses", "prohibited_uses")).map((item) => text(item)).filter(Boolean),
    schemaVersion: text(field(source, "schemaVersion", "schema_version"), "unknown"),
    rowCount: number(field(source, "rowCount", "row_count"), number(field(source, "itemCount", "item_count"))),
    hash: text(field(source, "hash"), text(field(source, "contentHash", "content_hash"))),
    releasedAt: nullableText(field(source, "releasedAt", "released_at")),
  };
}

function normalizeOverview(value: unknown): LearningOverview {
  const source = record(value);
  return {
    episodeCount: number(field(source, "episodeCount", "episode_count"), number(field(source, "episodes"))),
    activeEpisodeCount: number(field(source, "activeEpisodeCount", "active_episode_count")),
    environmentRunCount: number(field(source, "environmentRunCount", "environment_run_count"), number(field(source, "environmentRuns"))),
    activeEnvironmentRunCount: number(field(source, "activeEnvironmentRunCount", "active_environment_run_count")),
    aiRunCount: number(field(source, "aiRunCount", "ai_run_count"), number(field(source, "aiRuns"))),
    failedAiRunCount: number(field(source, "failedAiRunCount", "failed_ai_run_count")),
    datasetReleaseCount: number(field(source, "datasetReleaseCount", "dataset_release_count")),
    hardViolationCount: number(field(source, "hardViolationCount", "hard_violation_count"), number(field(source, "hardViolations"))),
  };
}

export function normalizeConsoleBootstrap(value: unknown): LearningConsoleBootstrap {
  const source = record(value);
  const rawEpisodes = list(field(source, "episodes") ?? field(source, "recentEpisodes", "recent_episodes"));
  const episodes = rawEpisodes.map(normalizeEpisode);
  const explicitDefinitions = list(field(source, "episodeDefinitions", "episode_definitions"));
  const derivedDefinitions = rawEpisodes.map((episode) => normalizeDefinition(field(record(episode), "definition")));
  const definitions = (explicitDefinitions.length ? explicitDefinitions.map(normalizeDefinition) : derivedDefinitions)
    .filter((definition, index, all) => definition.id && all.findIndex((candidate) => candidate.id === definition.id) === index);
  return {
    overview: normalizeOverview(field(source, "overview")),
    episodeDefinitions: definitions,
    episodes,
    runs: list(field(source, "runs") ?? field(source, "recentEnvironmentRuns", "recent_environment_runs")).map(normalizeRun),
    aiRuns: list(field(source, "aiRuns", "ai_runs") ?? field(source, "recentAiRuns", "recent_ai_runs")).map(normalizeAiRun),
    datasets: list(field(source, "datasets")).map(normalizeDataset),
  };
}

function normalizeResource(value: unknown): ObservationResource {
  const source = record(value);
  return {
    resourceType: text(field(source, "resourceType", "resource_type"), "Resource"),
    resourceIdentityHash: nullableText(field(source, "resourceIdentityHash", "resource_identity_hash")) ?? undefined,
    resourceVersion: field(source, "resourceVersion", "resource_version") as string | number | undefined,
    contentHash: nullableText(field(source, "contentHash", "content_hash")) ?? undefined,
    sensitivity: nullableText(field(source, "sensitivity")) ?? undefined,
  };
}

function normalizeOutcome(value: unknown): TrajectoryOutcome & { decisionId?: string; actionId?: string } {
  const source = record(value);
  const contentHash = nullableText(field(source, "contentHash", "content_hash"));
  return {
    type: text(field(source, "type"), text(field(source, "outcomeType", "outcome_type"), "outcome")),
    value: field(source, "value") ?? (contentHash ? { contentHash } : "Value withheld"),
    provenanceKind: text(field(source, "provenanceKind", "provenance_kind"), "unknown"),
    observedAt: text(field(source, "observedAt", "observed_at")),
    decisionId: nullableText(field(source, "decisionPointId", "decision_point_id")) ?? undefined,
    actionId: nullableText(field(source, "actionAttemptId", "action_attempt_id")) ?? undefined,
  };
}

export function normalizeEpisodeTrajectory(value: unknown): EpisodeTrajectory {
  const source = record(value);
  const pagination = record(field(source, "pagination"));
  const rawOutcomes = list(field(source, "outcomes")).map(normalizeOutcome);
  const rawEvents = list(field(source, "events")).map(record);
  const provisionalSteps = list(field(source, "steps"));
  const decisions = provisionalSteps.length ? provisionalSteps : list(field(source, "decisions"));
  return {
    episode: normalizeEpisode(field(source, "episode")),
    steps: decisions.map((item, index) => {
      const decision = record(item);
      const observation = record(field(decision, "observation"));
      const action = record(field(decision, "action") ?? field(decision, "selectedAction", "selected_action"));
      const actionId = text(field(action, "id"));
      const decisionId = text(field(decision, "id"));
      const ai = record(field(action, "aiProvenance", "ai_provenance"));
      const event = rawEvents.find((candidate) => number(field(candidate, "sequence")) === number(field(decision, "sequence"))) ?? {};
      const nestedOutcomes = list(field(decision, "outcomes")).map(normalizeOutcome);
      const matchedOutcomes = rawOutcomes.filter((outcome) => outcome.decisionId === decisionId || (actionId && outcome.actionId === actionId));
      return {
        sequence: number(field(decision, "sequence"), index + 1),
        decisionType: text(field(decision, "decisionType", "decision_type"), "decision"),
        openedAt: text(field(decision, "openedAt", "opened_at")),
        observation: {
          asOfAt: text(field(observation, "asOfAt", "as_of_at")),
          manifestHash: text(field(observation, "manifestHash", "manifest_hash")),
          syntheticSnapshot: Object.keys(record(field(observation, "syntheticSnapshot", "synthetic_snapshot"))).length ? record(field(observation, "syntheticSnapshot", "synthetic_snapshot")) : null,
          resources: list(field(observation, "resources")).map(normalizeResource),
        },
        availableActions: list(field(decision, "availableActions", "available_actions")).map((nested) => typeof nested === "string" ? nested : text(field(record(nested), "type"))).filter(Boolean),
        action: Object.keys(action).length ? {
          type: text(field(action, "type"), text(field(action, "actionType", "action_type"), "unknown")),
          status: text(field(action, "status"), "unknown"),
          actorKind: text(field(action, "actorKind", "actor_kind"), "unknown"),
          aiRunId: nullableText(field(action, "aiRunId", "ai_run_id")) ?? nullableText(field(ai, "id")),
        } : null,
        outcomes: nestedOutcomes.length ? nestedOutcomes : matchedOutcomes,
        event: Object.keys(event).length ? {
          type: text(field(event, "type"), text(field(event, "eventType", "event_type"), "event")),
          payloadHash: text(field(event, "payloadHash", "payload_hash")),
        } : null,
      };
    }),
    nextOffset: nullableNumber(field(pagination, "nextOffset", "next_offset")),
    evidenceTruncated: Boolean(
      field(pagination, "eventsTruncated", "events_truncated")
      || field(pagination, "outcomesTruncated", "outcomes_truncated"),
    ),
  };
}

export function normalizeRunHistory(value: unknown): RunHistory {
  const source = record(value);
  const pagination = record(field(source, "pagination"));
  const steps = list(field(source, "steps")).map((item, index) => {
    const step = record(item);
    const action = record(field(step, "action"));
    const ai = record(field(action, "aiProvenance", "ai_provenance") ?? field(step, "model"));
    const rewardObject = field(step, "reward");
    const rewardList = list(field(step, "rewards"));
    const rewards = rewardList.length
      ? Object.fromEntries(rewardList.map((entry) => {
          const reward = record(entry);
          return [text(field(reward, "componentName", "component_name"), "reward"), number(field(reward, "value"))];
        }))
      : numericRecord(rewardObject);
    return {
      sequence: number(field(step, "sequence"), number(field(step, "stepNumber", "step_number"), index + 1)),
      actionType: text(field(step, "actionType", "action_type"), text(field(action, "actionType", "action_type"), "No action")),
      actionStatus: text(field(step, "actionStatus", "action_status"), text(field(action, "status"), "unknown")),
      supportKind: text(field(step, "supportKind", "support_kind"), "unknown"),
      terminated: boolean(field(step, "terminated")),
      terminationReason: nullableText(field(step, "terminationReason", "termination_reason")),
      reward: rewards,
      hardViolations: list(field(step, "hardViolations", "hard_violations")).map((violation) => text(violation)),
      stateBeforeHash: nullableText(field(step, "stateBeforeHash", "state_before_hash")),
      stateAfterHash: nullableText(field(step, "stateAfterHash", "state_after_hash")),
      observationManifestHash: nullableText(field(record(field(step, "observation")), "manifestHash", "manifest_hash")),
      model: Object.keys(ai).length ? {
        provider: text(field(ai, "provider"), "unknown"),
        model: text(field(ai, "model"), "unknown"),
        fallbackUsed: boolean(field(ai, "fallbackUsed", "fallback_used")),
        latencyMs: field(ai, "latencyMs", "latency_ms") === null ? null : number(field(ai, "latencyMs", "latency_ms")),
      } : null,
    };
  });
  const run = normalizeRun(field(source, "run"));
  const modelSteps = steps.filter((step) => step.model !== null);
  if (modelSteps.some((step) => step.model?.fallbackUsed)) run.fallbackUsed = true;
  else if (modelSteps.length) run.fallbackUsed = false;
  return {
    run,
    steps,
    nextAfterStep: nullableNumber(field(pagination, "nextAfterStep", "next_after_step")),
  };
}

export function normalizeEnvironmentRunView(value: unknown): EnvironmentRunView {
  const run = record(field(record(value), "run"));
  return {
    run: {
      id: text(field(run, "id")),
      status: text(field(run, "status"), "unknown"),
      sequence: number(field(run, "sequence"), number(field(run, "currentStep", "current_step"))),
    },
  };
}

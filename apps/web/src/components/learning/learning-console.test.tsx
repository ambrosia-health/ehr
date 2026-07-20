import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LearningConsole } from "@/components/learning/learning-console";
import { ApiError, apiRequest } from "@/lib/api/client";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, apiRequest: vi.fn() };
});

const mockApiRequest = vi.mocked(apiRequest);

const definition = {
  id: "def-1",
  slug: "longitudinal-dermatology-operations",
  version: 1,
  name: "Longitudinal dermatology operations",
  description: "A synthetic end-to-end operations scenario.",
  episode_type: "longitudinal_service_journey",
  max_steps: 3,
  max_duration_seconds: 3600,
  action_types: ["review_intake", "review_pathology", "close_episode"],
  reward_components: ["safety", "task_completion"],
  released_at: "2026-07-17T12:00:00Z",
};

const episode = {
  id: "episode-1",
  source_kind: "synthetic",
  status: "running",
  seed: 17,
  started_at: "2026-07-17T12:01:00Z",
  ended_at: null,
  definition,
};

const run = {
  id: "run-0001",
  status: "running",
  mode: "simulation",
  agent_kind: "model_environment_agent",
  agent_model: "gpt-5-mini",
  seed: 17,
  current_step: 1,
  total_reward: { safety: 1, task_completion: 0.5 },
  hard_violation_count: 1,
  started_at: "2026-07-17T12:02:00Z",
  ended_at: null,
};

const bootstrap = {
  overview: {
    episode_count: 12,
    active_episode_count: 2,
    environment_run_count: 7,
    active_environment_run_count: 1,
    ai_run_count: 24,
    failed_ai_run_count: 1,
    dataset_release_count: 2,
    hard_violation_count: 1,
  },
  episode_definitions: [definition],
  recent_episodes: [episode],
  recent_environment_runs: [run],
  recent_ai_runs: [
    {
      id: "ai-1",
      capability: "environment_action_selection",
      provider: "openai",
      model: "gpt-5-mini",
      status: "succeeded",
      fallback_used: false,
      latency_ms: 321,
      started_at: "2026-07-17T12:03:00Z",
    },
  ],
  datasets: [
    {
      id: "dataset-1",
      name: "Synthetic trajectory preview",
      version: 1,
      schema_version: "learning-v1",
      status: "draft",
      classification: "synthetic",
      intended_uses: ["evaluation"],
      prohibited_uses: ["live_care_decisions"],
      content_hash: "dataset-hash-abc",
      item_count: 4,
      released_at: null,
    },
  ],
};

const trajectory = {
  episode,
  decisions: [
    {
      id: "decision-1",
      sequence: 1,
      decision_type: "environment.intake_review",
      opened_at: "2026-07-17T12:04:00Z",
      available_actions: ["review_intake", "escalate"],
      observation: {
        as_of_at: "2026-07-17T12:04:00Z",
        manifest_hash: "manifest-hash-123",
        synthetic_snapshot: { stage: "intake_review", urgent: false },
        resources: [
          {
            resource_type: "QuestionnaireResponse",
            resource_identity_hash: "resource-identity-hash",
            resource_version: 2,
            content_hash: "resource-content-hash",
          },
          {
            resource_type: "Encounter",
            resource_id: "raw-resource-id-must-not-render",
            snapshot_ref: "storage://locator-must-not-render",
            resource_version: 1,
          },
        ],
      },
      selected_action: {
        id: "action-1",
        action_type: "review_intake",
        status: "succeeded",
        actor_kind: "agent",
        ai_provenance: { id: "ai-1", provider: "openai", model: "gpt-5-mini" },
      },
    },
  ],
  events: [
    { sequence: 1, event_type: "environment.step", payload_hash: "event-payload-hash" },
  ],
  outcomes: [
    {
      decision_point_id: "decision-1",
      action_attempt_id: "action-1",
      outcome_type: "workflow_stage_transition",
      value: { from_stage: "intake_review", to_stage: "encounter_review" },
      provenance_kind: "simulated",
      observed_at: "2026-07-17T12:05:00Z",
    },
  ],
  pagination: { offset: 0, limit: 50, next_offset: null },
};

const history = {
  run,
  steps: [
    {
      step_number: 1,
      state_before_hash: "state-before-hash",
      state_after_hash: "state-after-hash",
      observation: { manifest_hash: "run-observation-hash" },
      support_kind: "simulated",
      terminated: false,
      termination_reason: null,
      action: {
        action_type: "review_intake",
        status: "succeeded",
        ai_provenance: {
          provider: "openai",
          model: "gpt-5-mini",
          fallback_used: true,
          latency_ms: 410,
        },
      },
      rewards: [
        { component_name: "safety", value: -1 },
        { component_name: "task_completion", value: 0.5 },
      ],
      hard_violations: ["unsafe_action"],
    },
  ],
  pagination: { after_step: 0, limit: 50, next_after_step: null },
};

describe("LearningConsole", () => {
  beforeEach(() => {
    mockApiRequest.mockReset();
  });

  it("opens a separate internal evidence console from the bounded bootstrap", async () => {
    const user = userEvent.setup();
    mockApiRequest.mockResolvedValue(bootstrap);

    render(<LearningConsole />);

    expect(await screen.findByRole("heading", { name: "Learning Console", level: 1 })).toBeVisible();
    expect(screen.getByText("12")).toBeVisible();
    expect(screen.getByText("24 AI runs · 1 failed")).toBeVisible();
    expect(screen.getByRole("tab", { name: "Trajectories" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Runs" })).toBeVisible();

    await user.click(screen.getByRole("tab", { name: "Datasets" }));
    expect(screen.getByRole("heading", { name: "Synthetic trajectory preview" })).toBeVisible();
    expect(screen.getByText("dataset-hash-abc")).toBeVisible();
    expect(screen.getByText("Live Care Decisions")).toBeVisible();
  });

  it("requests a presenter code after an unauthorized bootstrap and retries the console", async () => {
    const user = userEvent.setup();
    mockApiRequest
      .mockRejectedValueOnce(new ApiError("Presenter delegation is required.", 403))
      .mockResolvedValueOnce({ persona: "owner" })
      .mockResolvedValueOnce(bootstrap);

    render(<LearningConsole />);

    expect(await screen.findByRole("heading", { name: "Learning Console access" })).toBeVisible();
    await user.type(screen.getByLabelText("Presenter code"), "internal-demo-code");
    await user.click(screen.getByRole("button", { name: "Open console" }));

    expect(await screen.findByRole("heading", { name: "Learning Console", level: 1 })).toBeVisible();
    expect(mockApiRequest).toHaveBeenNthCalledWith(2, "/api/auth/demo/session", {
      method: "POST",
      body: { persona: "owner", presenterCode: "internal-demo-code" },
    });
  });

  it("reconstructs a trajectory from observations, actions, events, and outcomes", async () => {
    const user = userEvent.setup();
    mockApiRequest.mockImplementation(async (path) => {
      if (path === "/api/demo/learning/console") return bootstrap;
      if (path === "/api/demo/learning/episodes/episode-1/trajectory") return trajectory;
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<LearningConsole />);
    await user.click(await screen.findByRole("tab", { name: "Trajectories" }));

    expect(await screen.findByRole("heading", { name: /Environment.*Intake Review/ })).toBeVisible();
    expect(screen.getByText("manifest-hash-123")).toBeVisible();
    expect(screen.getByText("resource-content-hash")).toBeVisible();
    expect(screen.getByText("Reference withheld")).toBeVisible();
    expect(screen.queryByText("raw-resource-id-must-not-render")).not.toBeInTheDocument();
    expect(screen.queryByText("storage://locator-must-not-render")).not.toBeInTheDocument();
    expect(screen.getByText("review_intake")).toBeVisible();
    expect(screen.getByText("Workflow Stage Transition")).toBeVisible();
    expect(screen.getByText("event-payload-hash")).toBeVisible();

    await user.click(screen.getByRole("button", { name: /Longitudinal dermatology operations.*Synthetic.*Running/i }));
    expect(screen.queryByText("Loading decision timeline…")).not.toBeInTheDocument();
  });

  it("runs one model-selected step and renders provenance, rewards, and hard violations", async () => {
    const user = userEvent.setup();
    mockApiRequest.mockImplementation(async (path, options) => {
      if (path === "/api/demo/learning/console") return bootstrap;
      if (path === "/api/demo/learning/environment-runs/run-0001/history") return history;
      if (path === "/api/demo/learning/environment-runs/run-0001/model-step") {
        expect(options).toMatchObject({ method: "POST", body: { expectedSequence: 2 } });
        return { run: { id: "run-0001", status: "running", sequence: 2 } };
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<LearningConsole />);
    await user.click(await screen.findByRole("tab", { name: "Runs" }));

    expect((await screen.findAllByText("Fallback used", { selector: "span" })).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("unsafe_action")).toBeVisible();
    expect(screen.getByText("state-after-hash")).toBeVisible();
    const step = screen.getByText("STEP 1").closest("li");
    expect(step).not.toBeNull();
    expect(within(step!).getByText("-1.00")).toBeVisible();

    await user.click(screen.getByRole("button", { name: /Run run-0001/i }));
    expect(screen.queryByText("Loading complete run history…")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Run model step" }));
    expect(await screen.findByRole("status")).toHaveTextContent("One model step completed.");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "/api/demo/learning/environment-runs/run-0001/model-step",
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({ expectedSequence: 2, idempotencyKey: expect.stringMatching(/^console-model-step-/) }),
      }),
    );
  });

  it("creates a seeded synthetic run from a released episode definition", async () => {
    const user = userEvent.setup();
    const emptyBootstrap = { ...bootstrap, recent_environment_runs: [] };
    let consoleRequests = 0;
    mockApiRequest.mockImplementation(async (path, options) => {
      if (path === "/api/demo/learning/console") {
        consoleRequests += 1;
        return consoleRequests === 1 ? emptyBootstrap : bootstrap;
      }
      if (path === "/api/demo/learning/environment-runs") {
        expect(options).toMatchObject({
          method: "POST",
          body: { episodeDefinitionId: "def-1", actorRole: "environment_agent", seed: 17 },
        });
        return { run: { id: "run-0001", status: "running", sequence: 0 } };
      }
      if (path === "/api/demo/learning/environment-runs/run-0001/history") return { ...history, run: { ...run, current_step: 0 }, steps: [] };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<LearningConsole />);
    await user.click(await screen.findByRole("tab", { name: "Runs" }));
    await user.click(screen.getByRole("button", { name: "Create run" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Synthetic environment run created.");
    await waitFor(() => expect(mockApiRequest).toHaveBeenCalledWith(
      "/api/demo/learning/environment-runs",
      expect.objectContaining({ body: expect.objectContaining({ idempotencyKey: expect.stringMatching(/^console-run-/) }) }),
    ));
  });

  it("loads the next bounded trajectory page on demand", async () => {
    const user = userEvent.setup();
    const firstPage = {
      ...trajectory,
      pagination: { offset: 0, limit: 1, next_offset: 1 },
    };
    const secondPage = {
      ...trajectory,
      decisions: [{
        ...trajectory.decisions[0],
        id: "decision-2",
        sequence: 2,
        decision_type: "environment.encounter_review",
      }],
      events: [{ sequence: 2, event_type: "environment.step", payload_hash: "event-page-2" }],
      outcomes: [],
      pagination: { offset: 1, limit: 1, next_offset: null },
    };
    mockApiRequest.mockImplementation(async (path) => {
      if (path === "/api/demo/learning/console") return bootstrap;
      if (path === "/api/demo/learning/episodes/episode-1/trajectory") return firstPage;
      if (path === "/api/demo/learning/episodes/episode-1/trajectory?offset=1&limit=50") return secondPage;
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<LearningConsole />);
    await user.click(await screen.findByRole("tab", { name: "Trajectories" }));
    await user.click(await screen.findByRole("button", { name: "Load more decisions" }));

    expect(await screen.findByRole("heading", { name: /Environment.*Encounter Review/ })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Load more decisions" })).not.toBeInTheDocument();
  });

  it("makes bounded trajectory evidence truncation visible", async () => {
    const user = userEvent.setup();
    mockApiRequest.mockImplementation(async (path) => {
      if (path === "/api/demo/learning/console") return bootstrap;
      if (path === "/api/demo/learning/episodes/episode-1/trajectory") {
        return {
          ...trajectory,
          pagination: {
            ...trajectory.pagination,
            outcomes_truncated: true,
          },
        };
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<LearningConsole />);
    await user.click(await screen.findByRole("tab", { name: "Trajectories" }));

    expect(await screen.findByText(/reached its bounded evidence limit/i)).toBeVisible();
  });

  it("loads the next bounded run-history page on demand", async () => {
    const user = userEvent.setup();
    const firstPage = {
      ...history,
      pagination: { after_step: 0, limit: 1, next_after_step: 1 },
    };
    const secondPage = {
      ...history,
      run: { ...run, current_step: 2 },
      steps: [{ ...history.steps[0], step_number: 2, state_after_hash: "state-after-page-2" }],
      pagination: { after_step: 1, limit: 1, next_after_step: null },
    };
    mockApiRequest.mockImplementation(async (path) => {
      if (path === "/api/demo/learning/console") return bootstrap;
      if (path === "/api/demo/learning/environment-runs/run-0001/history") return firstPage;
      if (path === "/api/demo/learning/environment-runs/run-0001/history?after_step=1&limit=50") return secondPage;
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<LearningConsole />);
    await user.click(await screen.findByRole("tab", { name: "Runs" }));
    await user.click(await screen.findByRole("button", { name: "Load more steps" }));

    expect(await screen.findByText("STEP 2")).toBeVisible();
    expect(screen.getByText("state-after-page-2")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Load more steps" })).not.toBeInTheDocument();
  });
});

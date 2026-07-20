"use client";

import { Activity, Database, GitBranch, LoaderCircle, RotateCcw, ShieldCheck, TestTubes } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AccessGate } from "@/components/learning/access-gate";
import { DatasetsPanel } from "@/components/learning/datasets-panel";
import { normalizeConsoleBootstrap } from "@/components/learning/normalize";
import { OverviewPanel } from "@/components/learning/overview-panel";
import { RunsPanel } from "@/components/learning/runs-panel";
import { TrajectoriesPanel } from "@/components/learning/trajectories-panel";
import type { LearningConsoleBootstrap } from "@/components/learning/types";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, apiRequest } from "@/lib/api/client";

async function requestConsole(signal?: AbortSignal): Promise<LearningConsoleBootstrap> {
  const response = await apiRequest<unknown>("/api/demo/learning/console", { signal });
  return normalizeConsoleBootstrap(response);
}

export function LearningConsole() {
  const [data, setData] = useState<LearningConsoleBootstrap | null>(null);
  const [loading, setLoading] = useState(true);
  const [accessRequired, setAccessRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchConsole = useCallback(async (signal?: AbortSignal) => {
    try {
      setData(await requestConsole(signal));
      setAccessRequired(false);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 0 && signal?.aborted) return;
      if (caught instanceof ApiError && (caught.status === 401 || caught.status === 403)) {
        setAccessRequired(true);
        setData(null);
      } else {
        setError(caught instanceof Error ? caught.message : "The Learning Console could not be loaded.");
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  const loadConsole = useCallback(async () => {
    setLoading(true);
    setError(null);
    await fetchConsole();
  }, [fetchConsole]);

  useEffect(() => {
    const controller = new AbortController();
    void requestConsole(controller.signal)
      .then((response) => {
        setData(response);
        setAccessRequired(false);
      })
      .catch((caught: unknown) => {
        if (caught instanceof ApiError && caught.status === 0 && controller.signal.aborted) return;
        if (caught instanceof ApiError && (caught.status === 401 || caught.status === 403)) {
          setAccessRequired(true);
          setData(null);
        } else {
          setError(caught instanceof Error ? caught.message : "The Learning Console could not be loaded.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  if (accessRequired) return <AccessGate onAuthenticated={() => loadConsole()} />;

  if (loading && !data) {
    return (
      <div role="status" className="flex min-h-[24rem] items-center justify-center gap-2 text-sm text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        Loading learning evidence…
      </div>
    );
  }

  if (error && !data) {
    return (
      <section className="mx-auto mt-14 max-w-xl rounded-lg border border-safety/25 bg-card p-7 text-center" aria-labelledby="console-error-title">
        <h1 id="console-error-title" className="text-lg font-semibold">The Learning Console could not be opened</h1>
        <p role="alert" className="mt-2 text-sm text-muted-foreground">{error}</p>
        <Button type="button" className="mt-5" onClick={() => void loadConsole()}><RotateCcw className="size-4" aria-hidden="true" />Try again</Button>
      </section>
    );
  }

  if (!data) return null;

  return (
    <div>
      <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.1em] text-primary">
            <ShieldCheck className="size-3.5" aria-hidden="true" />
            Evidence debugger
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-[-0.035em] sm:text-3xl">Learning Console</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Inspect what was known, what was chosen, what happened next, and how synthetic model runs were scored.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-muted-foreground sm:inline">Read-only evidence · isolated simulation controls</span>
          <Button type="button" variant="outline" onClick={() => void loadConsole()} disabled={loading}>
            <RotateCcw className={loading ? "size-4 animate-spin" : "size-4"} aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </div>

      {error ? <p role="alert" className="mb-4 rounded-md border border-safety/25 bg-safety-muted px-3 py-2 text-sm text-safety">Refresh failed: {error}</p> : null}

      <Tabs defaultValue="overview">
        <div className="overflow-x-auto border-b border-border">
          <TabsList variant="line" aria-label="Learning Console sections" className="min-w-max pb-2">
            <TabsTrigger value="overview"><Activity className="size-3.5" aria-hidden="true" />Overview</TabsTrigger>
            <TabsTrigger value="trajectories"><GitBranch className="size-3.5" aria-hidden="true" />Trajectories</TabsTrigger>
            <TabsTrigger value="runs"><TestTubes className="size-3.5" aria-hidden="true" />Runs</TabsTrigger>
            <TabsTrigger value="datasets"><Database className="size-3.5" aria-hidden="true" />Datasets</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="overview" className="pt-5"><OverviewPanel overview={data.overview} aiRuns={data.aiRuns} /></TabsContent>
        <TabsContent value="trajectories" className="pt-5"><TrajectoriesPanel episodes={data.episodes} /></TabsContent>
        <TabsContent value="runs" className="pt-5"><RunsPanel episodeDefinitions={data.episodeDefinitions} runs={data.runs} onRefresh={() => loadConsole()} /></TabsContent>
        <TabsContent value="datasets" className="pt-5"><DatasetsPanel datasets={data.datasets} /></TabsContent>
      </Tabs>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";

import { useDemoSession } from "@/components/system/app-providers";
import { apiRequest, endpoints } from "@/lib/api/client";
import { ApiError } from "@/lib/api/client";
import type { ApiMode, DemoBootstrap } from "@/lib/api/types";

export const demoBootstrapQueryKey = ["demo-bootstrap"] as const;

export function useDemoBootstrap(): {
  data?: DemoBootstrap;
  mode: ApiMode;
  error: Error | null;
  refetch: () => void;
} {
  const { sessionLifecycle } = useDemoSession();
  const query = useQuery({
    queryKey: demoBootstrapQueryKey,
    queryFn: () => apiRequest<DemoBootstrap>(endpoints.bootstrap),
    enabled: sessionLifecycle === "active",
    retry: false,
    staleTime: 30_000,
  });

  if (sessionLifecycle === "ended") {
    return { data: undefined, mode: "error", error: new ApiError("Session ended", 401), refetch: () => undefined };
  }

  if (sessionLifecycle === "checking") {
    return { data: undefined, mode: "loading", error: null, refetch: () => undefined };
  }

  if (query.isPending) {
    return { data: undefined, mode: "loading", error: null, refetch: () => void query.refetch() };
  }

  if (query.error) {
    return { data: undefined, mode: "error", error: query.error, refetch: () => void query.refetch() };
  }

  return { data: query.data, mode: "live", error: null, refetch: () => void query.refetch() };
}

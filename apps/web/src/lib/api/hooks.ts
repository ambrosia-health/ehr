"use client";

import { useQuery } from "@tanstack/react-query";

import { useDemoSession } from "@/components/system/app-providers";
import { apiRequest, endpoints } from "@/lib/api/client";
import { ApiError } from "@/lib/api/client";
import type { ApiMode, DemoBootstrap } from "@/lib/api/types";
import { parseDemoBootstrap } from "@/lib/api/validation";

export const demoBootstrapQueryKey = ["demo-bootstrap"] as const;

export function useDemoBootstrap(): {
  data?: DemoBootstrap;
  mode: ApiMode;
  error: Error | null;
  refetch: () => Promise<void>;
} {
  const { sessionLifecycle } = useDemoSession();
  const query = useQuery({
    queryKey: demoBootstrapQueryKey,
    queryFn: async () => parseDemoBootstrap(await apiRequest<unknown>(endpoints.bootstrap)),
    enabled: sessionLifecycle === "active",
    retry: false,
    staleTime: 30_000,
  });

  if (sessionLifecycle === "ended") {
    return { data: undefined, mode: "error", error: new ApiError("Session ended", 401), refetch: async () => undefined };
  }

  if (sessionLifecycle === "checking") {
    return { data: undefined, mode: "loading", error: null, refetch: async () => undefined };
  }

  if (query.isPending) {
    return { data: undefined, mode: "loading", error: null, refetch: async () => { await query.refetch(); } };
  }

  if (query.error) {
    return { data: undefined, mode: "error", error: query.error, refetch: async () => { await query.refetch(); } };
  }

  return { data: query.data, mode: "live", error: null, refetch: async () => { await query.refetch(); } };
}

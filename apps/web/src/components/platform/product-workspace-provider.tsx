"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";

import { PageError, PageLoading } from "@/components/system/data-state";
import { ApiError, apiRequest } from "@/lib/api/client";

import { isProductWorkspace, type ProductWorkspace } from "./product-workspace";

interface ProductWorkspaceContextValue {
  workspace: ProductWorkspace;
  refresh: () => Promise<ProductWorkspace>;
}

const ProductWorkspaceContext = createContext<ProductWorkspaceContextValue | null>(null);

async function requestWorkspace(signal?: AbortSignal) {
  return apiRequest<unknown>("/api/demo/bootstrap", { signal });
}

async function loadProductWorkspace(signal?: AbortSignal): Promise<ProductWorkspace> {
  let response: unknown;
  try {
    response = await requestWorkspace(signal);
  } catch (error) {
    if (!(error instanceof ApiError) || ![401, 403].includes(error.status)) throw error;
  }

  if (!isProductWorkspace(response)) {
    await apiRequest("/api/auth/demo/session", {
      method: "POST",
      body: { persona: "provider" },
      signal,
    });
    response = await requestWorkspace(signal);
  }

  if (!isProductWorkspace(response)) {
    throw new ApiError("The API returned an incomplete clinician workspace.", 502, response);
  }
  return response;
}

interface ProductWorkspaceProviderProps extends PropsWithChildren {
  initialWorkspace?: ProductWorkspace;
}

export function ProductWorkspaceProvider({ children, initialWorkspace }: ProductWorkspaceProviderProps) {
  const [workspace, setWorkspace] = useState<ProductWorkspace | null>(initialWorkspace ?? null);
  const [error, setError] = useState<Error | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (initialWorkspace) return;
    const controller = new AbortController();

    void loadProductWorkspace(controller.signal)
      .then(setWorkspace)
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught : new Error("The clinician workspace could not be loaded."));
        }
      });

    return () => controller.abort();
  }, [initialWorkspace, retry]);

  const refresh = useCallback(async () => {
    const nextWorkspace = await loadProductWorkspace();
    setWorkspace(nextWorkspace);
    return nextWorkspace;
  }, []);

  const value = useMemo(() => workspace ? { workspace, refresh } : null, [refresh, workspace]);

  if (error) return <PageError error={error} retry={() => { setError(null); setRetry((attempt) => attempt + 1); }} />;
  if (!value) return <main className="mx-auto max-w-[1240px] px-6 py-10"><PageLoading label="Loading clinician workspace" /></main>;

  return <ProductWorkspaceContext.Provider value={value}>{children}</ProductWorkspaceContext.Provider>;
}

export function useProductWorkspace() {
  const value = useContext(ProductWorkspaceContext);
  if (!value) throw new Error("useProductWorkspace must be used within ProductWorkspaceProvider");
  return value;
}

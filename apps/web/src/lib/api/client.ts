import type { DemoActionResult } from "@/lib/api/types";
import {
  demoSessionExpiredEventName,
  markDemoSessionEnded,
} from "@/lib/auth/session-lifecycle";

const DEFAULT_API_TIMEOUT_MS = 30_000;

export const endpoints = {
  bootstrap: "/api/demo/bootstrap",
  demoSession: "/api/auth/demo/session",
  logout: "/api/auth/logout",
  switchPersona: "/api/auth/switch",
  intake: "/api/intake/submissions",
  resetDemo: "/api/demo/reset",
  advanceTime: "/api/demo/advance-time",
  triggerPathology: "/api/demo/triggers/pathology",
  triggerClaimResponse: "/api/demo/triggers/claim-response",
  encounterComplete: (encounterId: string) => `/api/encounters/${encounterId}/complete`,
  noteDraft: (noteId: string) => `/api/notes/${noteId}`,
  lesionObservation: "/api/lesions/observations",
  pathologyReview: (resultId: string) => `/api/pathology/results/${resultId}/review`,
  conversationRead: (conversationId: string) => `/api/conversations/${conversationId}/read`,
  conversationMessages: (conversationId: string) => `/api/conversations/${conversationId}/messages`,
  denialResubmit: (claimId: string) => `/api/claims/${claimId}/correct-and-resubmit`,
} as const;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  timeoutMs?: number;
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { body, headers, signal: callerSignal, timeoutMs = DEFAULT_API_TIMEOUT_MS, ...requestOptions } = options;
  let response: Response;
  let timedOut = false;
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort(callerSignal?.reason);
  if (callerSignal?.aborted) abortFromCaller();
  else callerSignal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    response = await fetch(path, {
      ...requestOptions,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "include",
      cache: "no-store",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...headers,
      },
    });
  } catch (error) {
    throw new ApiError(
      timedOut
        ? "The API request timed out. Please try again."
        : error instanceof Error
          ? error.message
          : "The API could not be reached.",
      0,
    );
  } finally {
    globalThis.clearTimeout(timeout);
    callerSignal?.removeEventListener("abort", abortFromCaller);
  }

  const contentType = response.headers.get("content-type") ?? "";
  let responseBody: unknown;
  try {
    responseBody = contentType.includes("application/json")
      ? await response.json()
      : await response.text();
  } catch {
    throw new ApiError("The API returned malformed JSON.", 502);
  }

  if (response.status === 401 && typeof window !== "undefined") {
    markDemoSessionEnded();
    window.dispatchEvent(new Event(demoSessionExpiredEventName));
  }

  if (!response.ok) {
    const detail = typeof responseBody === "object" && responseBody && "detail" in responseBody
      ? responseBody.detail
      : null;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)).join("; ")
        : `Request failed with status ${response.status}.`;
    throw new ApiError(message, response.status, responseBody);
  }

  if (!contentType.includes("application/json")) {
    throw new ApiError("The API returned a non-JSON success response.", 502, responseBody);
  }

  return responseBody as T;
}

export async function apiAction(
  path: string,
  body: unknown,
): Promise<DemoActionResult> {
  const response = await apiRequest<{ message?: string; at?: string }>(path, {
    method: "POST",
    body,
  });
  return {
    mode: "live",
    message: response.message ?? "Saved to the Ambrosia domain API.",
    at: response.at ?? new Date().toISOString(),
  };
}

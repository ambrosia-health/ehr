import type { DemoActionResult } from "@/lib/api/types";

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
  demoHealth: "/api/demo/health",
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
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { body, headers, ...requestOptions } = options;
  let response: Response;

  try {
    response = await fetch(path, {
      ...requestOptions,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "include",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...headers,
      },
    });
  } catch (error) {
    throw new ApiError(error instanceof Error ? error.message : "The API could not be reached.", 0);
  }

  const contentType = response.headers.get("content-type") ?? "";
  const responseBody = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof responseBody === "object" && responseBody && "detail" in responseBody
        ? String(responseBody.detail)
        : `Request failed with status ${response.status}.`;
    throw new ApiError(message, response.status, responseBody);
  }

  return responseBody as T;
}

export function isApiUnavailable(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 0 || error.status === 404 || error.status >= 500);
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

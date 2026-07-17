import {
  performanceNow,
  reportApiPerformance,
  type ApiPerformanceOutcome,
} from "@/lib/performance";

const DEFAULT_API_TIMEOUT_MS = 30_000;

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
  const startedAt = performanceNow();
  const method = (requestOptions.method ?? "GET").toUpperCase();
  let response: Response;
  let timedOut = false;
  let status = 0;
  let outcome: ApiPerformanceOutcome = "network_error";
  let requestId: string | undefined;
  let serverTiming: string | undefined;
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort(callerSignal?.reason);
  if (callerSignal?.aborted) abortFromCaller();
  else callerSignal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
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
      status = response.status;
      requestId = response.headers.get("x-request-id") ?? undefined;
      serverTiming = response.headers.get("server-timing") ?? undefined;
    } catch (error) {
      outcome = timedOut ? "timeout" : "network_error";
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
      outcome = "malformed_response";
      throw new ApiError("The API returned malformed JSON.", 502);
    }

    if (!response.ok) {
      outcome = "http_error";
      const detail = typeof responseBody === "object" && responseBody && "detail" in responseBody
        ? responseBody.detail
        : null;
      const message = typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)).join("; ")
          : "Request failed with status " + response.status + ".";
      throw new ApiError(message, response.status, responseBody);
    }

    if (!contentType.includes("application/json")) {
      outcome = "invalid_content_type";
      throw new ApiError("The API returned a non-JSON success response.", 502, responseBody);
    }

    outcome = "success";
    return responseBody as T;
  } finally {
    reportApiPerformance({
      path,
      method,
      status,
      outcome,
      startedAt,
      endedAt: performanceNow(),
      requestId,
      serverTiming,
    });
  }
}

export const demoSessionEndedStorageKey = "ambrosia.demo-session-ended";
export const demoSessionExpiredEventName = "ambrosia:session-expired";

export const demoSessionCookieNames = ["__Host-ambrosia_session", "ambrosia_session"] as const;

export type DemoSessionLifecycle = "checking" | "active" | "ended";

export function hasDemoSessionCookie(cookieStore: Pick<Map<string, unknown>, "has">): boolean {
  return demoSessionCookieNames.some((name) => cookieStore.has(name));
}

export function isDemoSessionMarkedEnded(): boolean {
  if (typeof window === "undefined") return false;

  try {
    return window.localStorage.getItem(demoSessionEndedStorageKey) === "1";
  } catch {
    return false;
  }
}

export function markDemoSessionEnded(): void {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.setItem(demoSessionEndedStorageKey, "1");
  } catch {
    // The in-memory lifecycle still denies access when storage is unavailable.
  }
}

export function markDemoSessionActive(): void {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.removeItem(demoSessionEndedStorageKey);
  } catch {
    // The in-memory lifecycle is authoritative for the current document.
  }
}

export function replaceWithLogin(): void {
  window.location.replace("/login");
}

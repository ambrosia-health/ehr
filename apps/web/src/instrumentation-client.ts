import { markRouteTransitionStart } from "./lib/performance";

if (typeof performance !== "undefined" && typeof performance.mark === "function") {
  performance.mark("ambrosia.app-init");
}

export function onRouterTransitionStart(url: string, navigationType: string) {
  markRouteTransitionStart(url, navigationType);
}

import type { DemoBootstrap } from "@/lib/api/types";

type Claim = DemoBootstrap["claims"][number];

export function selectDenialClaim(claims: Claim[]): Claim | undefined {
  const denialClaims = claims.filter((claim) => claim.denial);
  return denialClaims.find((claim) => claim.denial?.status === "open")
    ?? denialClaims.find((claim) => Boolean(claim.denial?.recovery?.submittedAt))
    ?? denialClaims.find((claim) => Boolean(claim.denial?.recovery))
    ?? denialClaims[0];
}

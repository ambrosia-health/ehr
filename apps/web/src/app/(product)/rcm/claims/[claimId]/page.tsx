import type { Metadata } from "next";

import { ClaimDetail } from "@/components/rcm/rcm-workspace";

export const metadata: Metadata = { title: "Claim detail" };

export default async function ClaimDetailPage({ params }: { params: Promise<{ claimId: string }> }) {
  const { claimId } = await params;
  return <ClaimDetail claimId={claimId} />;
}

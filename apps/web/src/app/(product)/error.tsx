"use client";

import { PageError } from "@/components/system/data-state";

export default function ProductError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <PageError error={error} retry={reset} />;
}

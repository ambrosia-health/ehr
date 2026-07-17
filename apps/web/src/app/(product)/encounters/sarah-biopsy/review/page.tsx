import type { Metadata } from "next";

import { ReviewComplete } from "@/components/provider/review-complete";

export const metadata: Metadata = { title: "Review and complete" };

export default function ReviewPage() {
  return <ReviewComplete />;
}

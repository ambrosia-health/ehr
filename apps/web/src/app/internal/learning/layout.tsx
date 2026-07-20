import type { Metadata } from "next";
import type { PropsWithChildren } from "react";

import { LearningShell } from "@/components/learning/learning-shell";

export const metadata: Metadata = {
  title: "Learning Console",
  description: "Internal trajectory and synthetic evaluation evidence console.",
  robots: { index: false, follow: false },
};

export default function LearningLayout({ children }: PropsWithChildren) {
  return <LearningShell>{children}</LearningShell>;
}

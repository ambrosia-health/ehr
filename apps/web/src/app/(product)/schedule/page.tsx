import type { Metadata } from "next";

import { ScheduleScreen } from "@/components/platform/schedule-screen";

export const metadata: Metadata = { title: "Schedule" };

export default function SchedulePage() {
  return <ScheduleScreen />;
}

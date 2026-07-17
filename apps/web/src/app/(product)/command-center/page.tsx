import type { Metadata } from "next";

import { TodayScreen } from "@/components/platform/today-screen";

export const metadata: Metadata = { title: "Today" };

export default function CommandCenterPage() {
  return <TodayScreen />;
}

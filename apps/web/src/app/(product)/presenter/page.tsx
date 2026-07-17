import type { Metadata } from "next";

import { PresenterConsole } from "@/components/presenter/presenter-console";

export const metadata: Metadata = { title: "Presenter console" };

export default function PresenterPage() {
  return <PresenterConsole />;
}

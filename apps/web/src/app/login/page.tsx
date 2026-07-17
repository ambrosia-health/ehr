import type { Metadata } from "next";

import { LoginScreen } from "@/components/product/login-screen";

export const metadata: Metadata = { title: "Demo sign in" };

export default function LoginPage() {
  return <LoginScreen />;
}

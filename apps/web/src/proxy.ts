import { NextResponse, type NextRequest } from "next/server";

import { hasDemoSessionCookie } from "@/lib/auth/session-lifecycle";

export function proxy(request: NextRequest) {
  if (hasDemoSessionCookie(request.cookies)) return NextResponse.next();

  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: [
    "/command-center/:path*",
    "/encounters/:path*",
    "/messages/:path*",
    "/mso/:path*",
    "/pathology/:path*",
    "/patient/:path*",
    "/patients/:path*",
    "/presenter/:path*",
    "/rcm/:path*",
  ],
};

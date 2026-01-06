import { NextResponse, type NextRequest } from "next/server";

// Auth disabled for MVP testing - all routes are public
export async function middleware(request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next|.*\\..*).*)"],
};

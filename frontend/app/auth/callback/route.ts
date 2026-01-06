/**
 * Auth Callback Route
 *
 * Auth disabled for MVP - redirects directly to app.
 */

import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { origin } = new URL(request.url);
  // Auth disabled for MVP - redirect to app directly
  return NextResponse.redirect(`${origin}/app`);
}

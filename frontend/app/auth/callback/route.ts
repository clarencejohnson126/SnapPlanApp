/**
 * Auth Callback Route
 *
 * Handles the email confirmation callback from Supabase.
 * Exchanges the auth code for a session and redirects to the app.
 */

import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/app";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  // Return the user to an error page with instructions
  return NextResponse.redirect(
    `${origin}/auth/login?message=Could not authenticate user`
  );
}

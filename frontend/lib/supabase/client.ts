/**
 * Supabase Browser Client
 *
 * Use this client in client components ('use client').
 * Creates a singleton client that persists across renders.
 */

import { createBrowserClient } from "@supabase/ssr";
import type { Database } from "./types";

let client: ReturnType<typeof createBrowserClient<Database>> | null = null;

export function createClient() {
  if (client) {
    return client;
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY environment variables"
    );
  }

  client = createBrowserClient<Database>(supabaseUrl, supabaseAnonKey);

  return client;
}

// Re-export for convenience
export { createClient as createBrowserClient };

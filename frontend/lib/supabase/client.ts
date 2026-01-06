/**
 * Supabase Browser Client
 *
 * Use this client in client components ('use client').
 * Creates a singleton client that persists across renders.
 * Returns null if Supabase is not configured (MVP mode).
 */

import { createBrowserClient as createSupabaseBrowserClient } from "@supabase/ssr";
import type { Database } from "./types";

let client: ReturnType<typeof createSupabaseBrowserClient<Database>> | null = null;

export function createClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  // Return null if Supabase is not configured (MVP mode without auth)
  if (!supabaseUrl || !supabaseAnonKey) {
    return null;
  }

  if (client) {
    return client;
  }

  client = createSupabaseBrowserClient<Database>(supabaseUrl, supabaseAnonKey);

  return client;
}

// Re-export for convenience
export { createClient as createBrowserClient };

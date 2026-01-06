/**
 * Supabase Client Exports
 *
 * Usage:
 * - Client components: import { createClient } from '@/lib/supabase/client'
 * - Server components/API: import { createClient } from '@/lib/supabase/server'
 */

// Re-export types
export * from "./types";

// Re-export client functions (named exports to avoid confusion)
export { createClient as createBrowserClient } from "./client";
export { createClient as createServerClient } from "./server";

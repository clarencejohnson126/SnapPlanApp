/**
 * Supabase Database Types
 *
 * These types are manually defined to match the MVP schema.
 * In production, use `supabase gen types typescript` to auto-generate.
 */

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export interface Database {
  public: {
    Tables: {
      projects: {
        Row: {
          id: string;
          user_id: string | null;
          name: string;
          description: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          user_id?: string | null;
          name: string;
          description?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string | null;
          name?: string;
          description?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      files: {
        Row: {
          id: string;
          project_id: string | null;
          user_id: string | null;
          original_filename: string;
          storage_path: string;
          file_type: string;
          file_size_bytes: number | null;
          mime_type: string | null;
          uploaded_by: string | null;
          uploaded_at: string;
        };
        Insert: {
          id?: string;
          project_id?: string | null;
          user_id?: string | null;
          original_filename: string;
          storage_path: string;
          file_type?: string;
          file_size_bytes?: number | null;
          mime_type?: string | null;
          uploaded_by?: string | null;
          uploaded_at?: string;
        };
        Update: {
          id?: string;
          project_id?: string | null;
          user_id?: string | null;
          original_filename?: string;
          storage_path?: string;
          file_type?: string;
          file_size_bytes?: number | null;
          mime_type?: string | null;
          uploaded_by?: string | null;
          uploaded_at?: string;
        };
      };
      jobs: {
        Row: {
          id: string;
          user_id: string;
          project_id: string;
          file_id: string;
          job_type: string;
          status: "queued" | "processing" | "completed" | "failed";
          config: Json | null;
          result_json: Json | null;
          total_area_m2: number | null;
          total_rooms: number | null;
          error_message: string | null;
          retry_count: number;
          queued_at: string;
          started_at: string | null;
          completed_at: string | null;
          processing_time_ms: number | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          project_id: string;
          file_id: string;
          job_type?: string;
          status?: "queued" | "processing" | "completed" | "failed";
          config?: Json | null;
          result_json?: Json | null;
          total_area_m2?: number | null;
          total_rooms?: number | null;
          error_message?: string | null;
          retry_count?: number;
          queued_at?: string;
          started_at?: string | null;
          completed_at?: string | null;
          processing_time_ms?: number | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          project_id?: string;
          file_id?: string;
          job_type?: string;
          status?: "queued" | "processing" | "completed" | "failed";
          config?: Json | null;
          result_json?: Json | null;
          total_area_m2?: number | null;
          total_rooms?: number | null;
          error_message?: string | null;
          retry_count?: number;
          queued_at?: string;
          started_at?: string | null;
          completed_at?: string | null;
          processing_time_ms?: number | null;
          created_at?: string;
        };
      };
      area_results: {
        Row: {
          id: string;
          job_id: string;
          room_id: string;
          room_name: string | null;
          room_type: string | null;
          area_m2: number;
          perimeter_m: number | null;
          ceiling_height_m: number | null;
          area_factor: number;
          effective_area_m2: number | null;
          source_text: string | null;
          source_page: number;
          source_bbox: Json | null;
          confidence: number;
          extraction_method: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          job_id: string;
          room_id: string;
          room_name?: string | null;
          room_type?: string | null;
          area_m2: number;
          perimeter_m?: number | null;
          ceiling_height_m?: number | null;
          area_factor?: number;
          effective_area_m2?: number | null;
          source_text?: string | null;
          source_page: number;
          source_bbox?: Json | null;
          confidence?: number;
          extraction_method?: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          job_id?: string;
          room_id?: string;
          room_name?: string | null;
          room_type?: string | null;
          area_m2?: number;
          perimeter_m?: number | null;
          ceiling_height_m?: number | null;
          area_factor?: number;
          effective_area_m2?: number | null;
          source_text?: string | null;
          source_page?: number;
          source_bbox?: Json | null;
          confidence?: number;
          extraction_method?: string;
          created_at?: string;
        };
      };
      job_totals: {
        Row: {
          id: string;
          job_id: string;
          total_rooms: number;
          total_area_m2: number;
          total_effective_area_m2: number;
          total_perimeter_m: number;
          area_by_type: Json | null;
          balcony_factor: number;
          computed_at: string;
        };
        Insert: {
          id?: string;
          job_id: string;
          total_rooms?: number;
          total_area_m2?: number;
          total_effective_area_m2?: number;
          total_perimeter_m?: number;
          area_by_type?: Json | null;
          balcony_factor?: number;
          computed_at?: string;
        };
        Update: {
          id?: string;
          job_id?: string;
          total_rooms?: number;
          total_area_m2?: number;
          total_effective_area_m2?: number;
          total_perimeter_m?: number;
          area_by_type?: Json | null;
          balcony_factor?: number;
          computed_at?: string;
        };
      };
      stripe_customers: {
        Row: {
          id: string;
          user_id: string;
          stripe_customer_id: string | null;
          email: string | null;
          name: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          stripe_customer_id?: string | null;
          email?: string | null;
          name?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          stripe_customer_id?: string | null;
          email?: string | null;
          name?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      subscriptions: {
        Row: {
          id: string;
          user_id: string;
          stripe_subscription_id: string | null;
          stripe_customer_id: string | null;
          status: string;
          plan_id: string | null;
          current_period_start: string | null;
          current_period_end: string | null;
          cancel_at: string | null;
          canceled_at: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          stripe_subscription_id?: string | null;
          stripe_customer_id?: string | null;
          status?: string;
          plan_id?: string | null;
          current_period_start?: string | null;
          current_period_end?: string | null;
          cancel_at?: string | null;
          canceled_at?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          stripe_subscription_id?: string | null;
          stripe_customer_id?: string | null;
          status?: string;
          plan_id?: string | null;
          current_period_start?: string | null;
          current_period_end?: string | null;
          cancel_at?: string | null;
          canceled_at?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      get_user_subscription: {
        Args: { p_user_id: string };
        Returns: {
          plan_id: string | null;
          status: string | null;
          current_period_end: string | null;
        }[];
      };
      user_has_active_subscription: {
        Args: { p_user_id: string };
        Returns: boolean;
      };
    };
    Enums: {
      [_ in never]: never;
    };
  };
}

// Convenience type exports
export type Project = Database["public"]["Tables"]["projects"]["Row"];
export type ProjectInsert = Database["public"]["Tables"]["projects"]["Insert"];
export type File = Database["public"]["Tables"]["files"]["Row"];
export type FileInsert = Database["public"]["Tables"]["files"]["Insert"];
export type Job = Database["public"]["Tables"]["jobs"]["Row"];
export type JobInsert = Database["public"]["Tables"]["jobs"]["Insert"];
export type AreaResult = Database["public"]["Tables"]["area_results"]["Row"];
export type JobTotals = Database["public"]["Tables"]["job_totals"]["Row"];

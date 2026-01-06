/**
 * SnapGrid Edge Function: process-job
 *
 * Orchestrates PDF extraction jobs:
 * 1. Receives job_id from Next.js API
 * 2. Fetches job details from database
 * 3. Gets signed URL for PDF from Storage
 * 4. Calls FastAPI backend for extraction
 * 5. Stores results in area_results and job_totals tables
 * 6. Updates job status
 *
 * Environment variables required:
 * - SUPABASE_URL (auto-injected)
 * - SUPABASE_SERVICE_ROLE_KEY (auto-injected)
 * - FASTAPI_URL (set in Edge Function secrets)
 */

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0";

// CORS headers for responses
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

// TypeScript interfaces
interface ProcessJobRequest {
  job_id: string;
}

interface JobRecord {
  id: string;
  user_id: string;
  project_id: string;
  file_id: string;
  job_type: string;
  status: string;
  config: Record<string, unknown>;
  files: {
    id: string;
    storage_path: string;
    original_filename: string;
  };
}

interface RoomResult {
  room_id: string;
  room_name: string | null;
  room_type: string | null;
  area_m2: number;
  perimeter_m: number | null;
  ceiling_height_m: number | null;
  area_factor: number;
  effective_area_m2: number;
  source_text: string | null;
  source_page: number;
  source_bbox: Record<string, number> | null;
  confidence: number;
  extraction_method: string;
}

interface FastAPIResponse {
  job_id: string;
  status: string;
  rooms: RoomResult[];
  total_rooms: number;
  total_area_m2: number;
  total_effective_area_m2: number;
  total_perimeter_m: number;
  area_by_type: Record<string, number>;
  processing_time_ms: number;
  warnings: string[];
}

serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Get environment variables
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const fastApiUrl = Deno.env.get("FASTAPI_URL") || "http://localhost:8000";

  if (!supabaseUrl || !supabaseServiceKey) {
    return new Response(
      JSON.stringify({ error: "Missing Supabase configuration" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  // Create Supabase client with service role (bypasses RLS)
  const supabase = createClient(supabaseUrl, supabaseServiceKey);

  let jobId: string | undefined;

  try {
    // Parse request body
    const body: ProcessJobRequest = await req.json();
    jobId = body.job_id;

    if (!jobId) {
      throw new Error("job_id is required");
    }

    console.log(`[process-job] Starting job: ${jobId}`);

    // 1. Fetch job details with file info
    const { data: job, error: jobError } = await supabase
      .from("jobs")
      .select(
        `
        *,
        files (
          id,
          storage_path,
          original_filename
        )
      `
      )
      .eq("id", jobId)
      .single<JobRecord>();

    if (jobError || !job) {
      throw new Error(`Job not found: ${jobId}. Error: ${jobError?.message}`);
    }

    console.log(`[process-job] Found job: ${job.job_type}, file: ${job.files.storage_path}`);

    // 2. Update status to processing
    const { error: updateError } = await supabase
      .from("jobs")
      .update({
        status: "processing",
        started_at: new Date().toISOString(),
      })
      .eq("id", jobId);

    if (updateError) {
      console.error(`[process-job] Failed to update status: ${updateError.message}`);
    }

    // 3. Get signed URL for the file (valid for 1 hour)
    const { data: signedUrlData, error: urlError } = await supabase.storage
      .from("snapgrid-files")
      .createSignedUrl(job.files.storage_path, 3600);

    if (urlError || !signedUrlData?.signedUrl) {
      throw new Error(
        `Failed to get signed URL for ${job.files.storage_path}: ${urlError?.message}`
      );
    }

    console.log(`[process-job] Got signed URL, calling FastAPI...`);

    // 4. Call FastAPI to process the job
    const fastApiResponse = await fetch(`${fastApiUrl}/api/v1/jobs/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        job_id: jobId,
        file_url: signedUrlData.signedUrl,
        job_type: job.job_type,
        config: job.config || {},
      }),
    });

    if (!fastApiResponse.ok) {
      const errorText = await fastApiResponse.text();
      throw new Error(`FastAPI error (${fastApiResponse.status}): ${errorText}`);
    }

    const result: FastAPIResponse = await fastApiResponse.json();
    console.log(`[process-job] FastAPI returned ${result.total_rooms} rooms`);

    // 5. Insert area_results
    if (result.rooms && result.rooms.length > 0) {
      const areaResults = result.rooms.map((room) => ({
        job_id: jobId,
        room_id: room.room_id,
        room_name: room.room_name,
        room_type: room.room_type,
        area_m2: room.area_m2,
        perimeter_m: room.perimeter_m,
        ceiling_height_m: room.ceiling_height_m,
        area_factor: room.area_factor,
        effective_area_m2: room.effective_area_m2,
        source_text: room.source_text,
        source_page: room.source_page,
        source_bbox: room.source_bbox,
        confidence: room.confidence,
        extraction_method: room.extraction_method,
      }));

      const { error: insertError } = await supabase
        .from("area_results")
        .insert(areaResults);

      if (insertError) {
        console.error(`[process-job] Failed to insert area_results: ${insertError.message}`);
        // Don't throw - we still want to update the job status
      } else {
        console.log(`[process-job] Inserted ${areaResults.length} area_results`);
      }
    }

    // 6. Insert job_totals
    const { error: totalsError } = await supabase.from("job_totals").insert({
      job_id: jobId,
      total_rooms: result.total_rooms,
      total_area_m2: result.total_area_m2,
      total_effective_area_m2: result.total_effective_area_m2,
      total_perimeter_m: result.total_perimeter_m,
      area_by_type: result.area_by_type,
      balcony_factor: (job.config as { balcony_factor?: number })?.balcony_factor || 0.5,
    });

    if (totalsError) {
      console.error(`[process-job] Failed to insert job_totals: ${totalsError.message}`);
    }

    // 7. Update job as completed
    const { error: completeError } = await supabase
      .from("jobs")
      .update({
        status: "completed",
        completed_at: new Date().toISOString(),
        processing_time_ms: result.processing_time_ms,
        result_json: result,
        total_area_m2: result.total_area_m2,
        total_rooms: result.total_rooms,
      })
      .eq("id", jobId);

    if (completeError) {
      console.error(`[process-job] Failed to update job completion: ${completeError.message}`);
    }

    console.log(`[process-job] Job ${jobId} completed successfully`);

    return new Response(
      JSON.stringify({
        success: true,
        job_id: jobId,
        total_rooms: result.total_rooms,
        total_area_m2: result.total_area_m2,
        processing_time_ms: result.processing_time_ms,
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(`[process-job] Error: ${errorMessage}`);

    // Update job as failed if we have job_id
    if (jobId && supabaseUrl && supabaseServiceKey) {
      try {
        const supabase = createClient(supabaseUrl, supabaseServiceKey);
        await supabase
          .from("jobs")
          .update({
            status: "failed",
            error_message: errorMessage,
            completed_at: new Date().toISOString(),
          })
          .eq("id", jobId);
      } catch (updateError) {
        console.error(`[process-job] Failed to update job failure status: ${updateError}`);
      }
    }

    return new Response(JSON.stringify({ error: errorMessage }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});

/**
 * API helper functions for SnapPlan frontend.
 */

import { ExtractionResponse, ExtractParams } from "./types";

/**
 * Get the backend API URL from environment variable.
 */
function getApiUrl(): string {
  const url = process.env.NEXT_PUBLIC_SNAPGRID_API_URL;
  if (!url) {
    throw new Error(
      "NEXT_PUBLIC_SNAPGRID_API_URL environment variable is not set"
    );
  }
  return url;
}

/**
 * Extract schedule data from a PDF file or sample.
 *
 * @param params - Extraction parameters
 * @param params.useSample - If true, use the built-in sample PDF
 * @param params.file - Optional file to upload (ignored if useSample is true)
 * @returns Promise<ExtractionResponse>
 */
export async function extractSchedule(
  params: ExtractParams
): Promise<ExtractionResponse> {
  const apiUrl = getApiUrl();
  const endpoint = `${apiUrl}/api/v1/schedules/extract`;

  // Build query params
  const queryParams = new URLSearchParams();
  queryParams.set("include_summary", "true");

  if (params.useSample) {
    queryParams.set("use_sample", "true");
  }

  const url = `${endpoint}?${queryParams.toString()}`;

  let response: Response;

  if (params.useSample || !params.file) {
    // No file upload - simple POST
    response = await fetch(url, {
      method: "POST",
    });
  } else {
    // File upload - multipart form data
    const formData = new FormData();
    formData.append("file", params.file);

    response = await fetch(url, {
      method: "POST",
      body: formData,
    });
  }

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error (${response.status}): ${errorText}`);
  }

  const data: ExtractionResponse = await response.json();
  return data;
}

/**
 * Check if the backend API is healthy.
 */
export async function checkApiHealth(): Promise<boolean> {
  try {
    const apiUrl = getApiUrl();
    const response = await fetch(`${apiUrl}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

"use client";

import { PersistenceInfo as PersistenceInfoType } from "@/lib/types";

interface PersistenceInfoProps {
  persistence: PersistenceInfoType;
}

export default function PersistenceInfo({ persistence }: PersistenceInfoProps) {
  return (
    <div className="persistence-info">
      <h2>Persistence Info</h2>

      <div className="persistence-status">
        <span className={`status-badge ${persistence.supabase_enabled ? "enabled" : "disabled"}`}>
          Supabase: {persistence.supabase_enabled ? "Enabled" : "Disabled"}
        </span>

        {persistence.supabase_enabled && persistence.success !== undefined && (
          <span className={`status-badge ${persistence.success ? "success" : "failed"}`}>
            {persistence.success ? "Saved" : "Failed"}
          </span>
        )}
      </div>

      {persistence.supabase_enabled && persistence.success && (
        <div className="persistence-details">
          <div className="detail-row">
            <span className="detail-label">File ID:</span>
            <code className="detail-value">{persistence.file_id || "N/A"}</code>
          </div>
          <div className="detail-row">
            <span className="detail-label">Extraction ID:</span>
            <code className="detail-value">{persistence.extraction_id || "N/A"}</code>
          </div>
          <div className="detail-row">
            <span className="detail-label">Storage Path:</span>
            <code className="detail-value">{persistence.storage_path || "N/A"}</code>
          </div>
        </div>
      )}

      {persistence.error && (
        <div className="persistence-error">
          <strong>Error:</strong> {persistence.error}
        </div>
      )}
    </div>
  );
}

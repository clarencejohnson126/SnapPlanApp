"use client";

import { ExtractionSummary } from "@/lib/types";

interface SummaryViewProps {
  summary: ExtractionSummary;
}

export default function SummaryView({ summary }: SummaryViewProps) {
  // Get unique dimensions
  const uniqueWidths = [...new Set(summary.dimensions.widths)].sort(
    (a, b) => a - b
  );
  const uniqueHeights = [...new Set(summary.dimensions.heights)].sort(
    (a, b) => a - b
  );

  return (
    <div className="summary-view">
      <h2>Extraction Summary</h2>

      <div className="summary-grid">
        <div className="summary-card">
          <h3>Total Doors</h3>
          <p className="summary-value">{summary.total_doors}</p>
        </div>

        <div className="summary-card">
          <h3>Door Types</h3>
          <ul className="summary-list">
            {Object.entries(summary.by_type).map(([type, count]) => (
              <li key={type}>
                <span className="type-name">{type || "Unknown"}</span>
                <span className="type-count">{count}</span>
              </li>
            ))}
          </ul>
        </div>

        {Object.keys(summary.by_fire_rating).length > 0 && (
          <div className="summary-card">
            <h3>Fire Ratings</h3>
            <ul className="summary-list">
              {Object.entries(summary.by_fire_rating).map(([rating, count]) => (
                <li key={rating}>
                  <span className="type-name">{rating}</span>
                  <span className="type-count">{count}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="summary-card">
          <h3>Dimensions</h3>
          <div className="dimensions">
            <p>
              <strong>Widths:</strong>{" "}
              {uniqueWidths.map((w) => `${w}m`).join(", ") || "N/A"}
            </p>
            <p>
              <strong>Heights:</strong>{" "}
              {uniqueHeights.map((h) => `${h}m`).join(", ") || "N/A"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

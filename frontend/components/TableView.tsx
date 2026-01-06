"use client";

import { ExtractedTable } from "@/lib/types";

interface TableViewProps {
  table: ExtractedTable;
}

export default function TableView({ table }: TableViewProps) {
  // Use normalized headers for display
  const headers = table.normalized_headers;

  // Format cell value for display
  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return "-";
    if (typeof value === "number") return value.toString();
    return String(value);
  };

  return (
    <div className="table-view">
      <h2>
        Extracted Table (Page {table.page_number})
      </h2>
      <p className="table-meta">
        {table.row_count} rows | Method: {table.extraction_method} | Confidence:{" "}
        {(table.confidence * 100).toFixed(0)}%
      </p>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              {headers.map((header, idx) => (
                <th key={idx}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIdx) => (
              <tr key={rowIdx}>
                {headers.map((header, colIdx) => {
                  const cell = row[header];
                  return (
                    <td key={colIdx} title={cell?.raw || ""}>
                      {cell ? formatValue(cell.value) : "-"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {table.warnings.length > 0 && (
        <div className="table-warnings">
          <h4>Warnings:</h4>
          <ul>
            {table.warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

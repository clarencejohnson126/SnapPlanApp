"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { useDropzone } from "react-dropzone";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  Upload,
  FileText,
  CheckCircle,
  AlertCircle,
  Download,
  ChevronRight,
  ChevronDown,
  Loader2,
  BarChart3,
  Table,
  Info,
  FileSpreadsheet,
  FileDown,
} from "lucide-react";
import {
  extractRooms,
  exportToExcel,
  exportToCSV,
  generateCSV,
  formatArea,
  formatNumber,
  getCategoryDisplayName,
  getStyleDisplayName,
  type ExtractionResult,
  type ExtractedRoom,
} from "@/lib/api";

type Step = "upload" | "processing" | "results";
type ResultTab = "table" | "charts";

// Colors for categories
const CATEGORY_COLORS: Record<string, string> = {
  office: "#3B82F6",
  residential: "#10B981",
  circulation: "#F59E0B",
  stairs: "#8B5CF6",
  elevators: "#EC4899",
  shafts: "#6366F1",
  technical: "#14B8A6",
  sanitary: "#06B6D4",
  storage: "#84CC16",
  outdoor: "#22C55E",
  other: "#64748B",
};

export default function ScanPage() {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [selectedRoom, setSelectedRoom] = useState<ExtractedRoom | null>(null);
  const [activeTab, setActiveTab] = useState<ResultTab>("table");
  const [isExporting, setIsExporting] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);

  // Handle file drop
  const onDrop = useCallback((acceptedFiles: File[]) => {
    const pdfFile = acceptedFiles.find(
      (f) => f.type === "application/pdf" || f.name.endsWith(".pdf")
    );
    if (pdfFile) {
      setFile(pdfFile);
      setError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
  });

  // Start extraction
  const handleStartExtraction = async () => {
    if (!file) return;

    setStep("processing");
    setError(null);

    try {
      const data = await extractRooms(file);
      setResult(data);
      setStep("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed");
      setStep("upload");
    }
  };

  // Download helper
  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Export to Excel
  const handleExportExcel = async () => {
    if (!result) return;
    setIsExporting(true);
    setShowExportMenu(false);
    try {
      const blob = await exportToExcel(result, file?.name || "SnapPlan Export");
      downloadBlob(blob, `${file?.name?.replace(".pdf", "") || "snapplan"}-export.xlsx`);
    } catch (err) {
      console.error("Excel export failed:", err);
    } finally {
      setIsExporting(false);
    }
  };

  // Export to CSV
  const handleExportCSV = async () => {
    if (!result) return;
    setIsExporting(true);
    setShowExportMenu(false);
    try {
      // Try backend first, fallback to client-side
      let blob: Blob;
      try {
        blob = await exportToCSV(result);
      } catch {
        blob = generateCSV(result);
      }
      downloadBlob(blob, `${file?.name?.replace(".pdf", "") || "snapplan"}-export.csv`);
    } catch (err) {
      console.error("CSV export failed:", err);
    } finally {
      setIsExporting(false);
    }
  };

  // Export to PDF (client-side table generation)
  const handleExportPDF = () => {
    if (!result) return;
    setShowExportMenu(false);

    // Create printable HTML
    const printContent = `
      <!DOCTYPE html>
      <html>
        <head>
          <title>SnapPlan Export - ${file?.name || 'Report'}</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 40px; }
            h1 { color: #0F1B2A; margin-bottom: 10px; }
            h2 { color: #64748B; font-weight: normal; margin-top: 0; }
            .summary { display: flex; gap: 40px; margin: 30px 0; padding: 20px; background: #f8fafc; border-radius: 8px; }
            .summary-item { }
            .summary-label { color: #64748B; font-size: 14px; }
            .summary-value { font-size: 28px; font-weight: bold; color: #0F1B2A; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th { background: #0F1B2A; color: white; text-align: left; padding: 12px 8px; font-size: 12px; }
            td { padding: 10px 8px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }
            tr:nth-child(even) { background: #f8fafc; }
            .number { text-align: right; font-family: monospace; }
            .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #94A3B8; font-size: 12px; }
          </style>
        </head>
        <body>
          <h1>Room Area Report</h1>
          <h2>${file?.name || 'SnapPlan Export'}</h2>

          <div class="summary">
            <div class="summary-item">
              <div class="summary-label">Total Rooms</div>
              <div class="summary-value">${result.room_count}</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">Total Area</div>
              <div class="summary-value">${result.total_area_m2.toFixed(2)} m²</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">Counted Area</div>
              <div class="summary-value">${result.total_counted_m2.toFixed(2)} m²</div>
            </div>
          </div>

          <table>
            <thead>
              <tr>
                <th>Room Number</th>
                <th>Room Name</th>
                <th>Category</th>
                <th class="number">Area (m²)</th>
                <th class="number">Factor</th>
                <th class="number">Counted (m²)</th>
                <th class="number">Page</th>
              </tr>
            </thead>
            <tbody>
              ${result.rooms.map(room => `
                <tr>
                  <td>${room.room_number}</td>
                  <td>${room.room_name}</td>
                  <td>${getCategoryDisplayName(room.category)}</td>
                  <td class="number">${room.area_m2.toFixed(2)}</td>
                  <td class="number">${(room.factor * 100).toFixed(0)}%</td>
                  <td class="number">${room.counted_m2.toFixed(2)}</td>
                  <td class="number">${room.page}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>

          <div class="footer">
            Generated by SnapPlan on ${new Date().toLocaleDateString('de-DE')} at ${new Date().toLocaleTimeString('de-DE')}
          </div>
        </body>
      </html>
    `;

    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(printContent);
      printWindow.document.close();
      printWindow.print();
    }
  };

  // Reset and start over
  const handleReset = () => {
    setStep("upload");
    setFile(null);
    setResult(null);
    setSelectedRoom(null);
    setError(null);
  };

  // Prepare chart data
  const getCategoryChartData = () => {
    if (!result) return [];
    return Object.entries(result.totals_by_category)
      .map(([category, area]) => ({
        name: getCategoryDisplayName(category),
        value: area,
        color: CATEGORY_COLORS[category] || CATEGORY_COLORS.other,
      }))
      .sort((a, b) => b.value - a.value);
  };

  const getPageChartData = () => {
    if (!result) return [];
    const byPage: Record<number, number> = {};
    result.rooms.forEach((room) => {
      byPage[room.page] = (byPage[room.page] || 0) + room.area_m2;
    });
    return Object.entries(byPage).map(([page, area]) => ({
      name: `Page ${page}`,
      area,
    }));
  };

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Quick Scan</h1>
          <p className="text-[#94A3B8] mt-1">
            Extract room areas from floor plans instantly
          </p>
        </div>
        {step === "results" && (
          <div className="flex items-center gap-3">
            <button
              onClick={handleReset}
              className="px-4 py-2.5 rounded-lg border border-white/10 text-[#94A3B8] hover:text-white hover:border-white/20 transition-colors"
            >
              New Scan
            </button>
            {/* Export Dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowExportMenu(!showExportMenu)}
                disabled={isExporting}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#00D4AA] text-[#0F1B2A] font-semibold hover:bg-[#00D4AA]/90 disabled:opacity-50 transition-colors"
              >
                {isExporting ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Download className="w-5 h-5" />
                )}
                Export
                <ChevronDown className="w-4 h-4" />
              </button>
              {showExportMenu && (
                <div className="absolute right-0 mt-2 w-48 bg-[#1A2942] border border-white/10 rounded-lg shadow-xl z-50 overflow-hidden">
                  <button
                    onClick={handleExportExcel}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-white hover:bg-white/5 transition-colors"
                  >
                    <FileSpreadsheet className="w-5 h-5 text-[#10B981]" />
                    <div>
                      <div className="font-medium">Excel</div>
                      <div className="text-xs text-[#64748B]">.xlsx file</div>
                    </div>
                  </button>
                  <button
                    onClick={handleExportCSV}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-white hover:bg-white/5 transition-colors border-t border-white/5"
                  >
                    <FileDown className="w-5 h-5 text-[#3B82F6]" />
                    <div>
                      <div className="font-medium">CSV</div>
                      <div className="text-xs text-[#64748B]">.csv file</div>
                    </div>
                  </button>
                  <button
                    onClick={handleExportPDF}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-white hover:bg-white/5 transition-colors border-t border-white/5"
                  >
                    <FileText className="w-5 h-5 text-[#EF4444]" />
                    <div>
                      <div className="font-medium">PDF</div>
                      <div className="text-xs text-[#64748B]">Print to PDF</div>
                    </div>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-4 mb-8">
        {[
          { key: "upload", label: "Upload" },
          { key: "processing", label: "Processing" },
          { key: "results", label: "Results" },
        ].map((s, i) => (
          <div key={s.key} className="flex items-center gap-4">
            <div
              className={`flex items-center gap-2 ${
                step === s.key
                  ? "text-[#00D4AA]"
                  : step === "results" || (step === "processing" && i < 1)
                    ? "text-white"
                    : "text-[#64748B]"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  step === s.key
                    ? "bg-[#00D4AA] text-[#0F1B2A]"
                    : step === "results" || (step === "processing" && i < 1)
                      ? "bg-[#00D4AA]/20 text-[#00D4AA]"
                      : "bg-[#1A2942] text-[#64748B]"
                }`}
              >
                {step === "results" || (step === "processing" && i < 1) ? (
                  <CheckCircle className="w-4 h-4" />
                ) : (
                  i + 1
                )}
              </div>
              <span className="font-medium">{s.label}</span>
            </div>
            {i < 2 && <ChevronRight className="w-5 h-5 text-[#64748B]" />}
          </div>
        ))}
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 mt-0.5" />
          <div>
            <p className="text-sm text-red-400 font-medium">Extraction Failed</p>
            <p className="text-sm text-red-400/80 mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Upload Step */}
      {step === "upload" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Dropzone */}
          <div
            {...getRootProps()}
            className={`relative border-2 border-dashed rounded-xl p-12 text-center transition-all cursor-pointer ${
              isDragActive
                ? "border-[#00D4AA] bg-[#00D4AA]/5"
                : file
                  ? "border-[#00D4AA]/50 bg-[#00D4AA]/5"
                  : "border-white/20 hover:border-white/40"
            }`}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col items-center">
              <div
                className={`w-20 h-20 rounded-full flex items-center justify-center mb-6 ${
                  file ? "bg-[#00D4AA]/20" : "bg-[#1A2942]"
                }`}
              >
                {file ? (
                  <FileText className="w-10 h-10 text-[#00D4AA]" />
                ) : (
                  <Upload className="w-10 h-10 text-[#94A3B8]" />
                )}
              </div>

              {file ? (
                <>
                  <h3 className="text-lg font-medium text-white mb-2">
                    {file.name}
                  </h3>
                  <p className="text-sm text-[#94A3B8]">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                  <p className="text-sm text-[#00D4AA] mt-2">
                    Click or drop to replace
                  </p>
                </>
              ) : (
                <>
                  <h3 className="text-lg font-medium text-white mb-2">
                    {isDragActive ? "Drop to upload" : "Drop PDF here or click to browse"}
                  </h3>
                  <p className="text-sm text-[#64748B]">
                    Support for CAD-exported floor plans
                  </p>
                </>
              )}
            </div>
          </div>

          {/* Configuration Panel */}
          <div className="bg-[#1A2942] rounded-xl border border-white/5 p-6">
            <h2 className="text-lg font-semibold text-white mb-6">
              Extraction Settings
            </h2>

            <div className="space-y-6">
              {/* Auto-detect info */}
              <div className="p-4 rounded-lg bg-[#0F1B2A] border border-white/5">
                <div className="flex items-start gap-3">
                  <Info className="w-5 h-5 text-[#00D4AA] mt-0.5" />
                  <div>
                    <p className="text-sm text-white font-medium">
                      Auto-Detection Enabled
                    </p>
                    <p className="text-xs text-[#94A3B8] mt-1">
                      Blueprint style (Haardtring, LeiQ, Omniturm) is automatically
                      detected based on text patterns.
                    </p>
                  </div>
                </div>
              </div>

              {/* Supported patterns */}
              <div>
                <label className="block text-sm font-medium text-[#94A3B8] mb-3">
                  Supported Patterns
                </label>
                <div className="space-y-2">
                  {[
                    { pattern: "NRF:", desc: "Netto-Raumfläche (Office)" },
                    { pattern: "F:", desc: "Fläche (Residential)" },
                    { pattern: "NGF:", desc: "Netto-Grundfläche (Highrise)" },
                  ].map((p) => (
                    <div
                      key={p.pattern}
                      className="flex items-center justify-between p-3 rounded-lg bg-[#0F1B2A]"
                    >
                      <code className="text-[#00D4AA] font-mono text-sm">
                        {p.pattern}
                      </code>
                      <span className="text-xs text-[#64748B]">{p.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Balcony factor info */}
              <div className="p-4 rounded-lg bg-[#0F1B2A] border border-white/5">
                <p className="text-sm text-[#94A3B8]">
                  <span className="text-white font-medium">Balcony Factor: </span>
                  Outdoor areas (Balkon, Terrasse, Loggia) are automatically
                  detected and counted at 50%.
                </p>
              </div>

              <hr className="border-white/5" />

              {/* Start button */}
              <button
                onClick={handleStartExtraction}
                disabled={!file}
                className="w-full py-3 px-4 rounded-lg bg-[#00D4AA] text-[#0F1B2A] font-semibold hover:bg-[#00D4AA]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                Start Extraction
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Processing Step */}
      {step === "processing" && (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="w-24 h-24 rounded-full bg-[#00D4AA]/10 flex items-center justify-center mb-6">
            <Loader2 className="w-12 h-12 text-[#00D4AA] animate-spin" />
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">
            Extracting Room Areas
          </h2>
          <p className="text-[#94A3B8] text-center max-w-md">
            Analyzing {file?.name}...
            <br />
            This usually takes 5-15 seconds.
          </p>
        </div>
      )}

      {/* Results Step */}
      {step === "results" && result && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-[#1A2942] rounded-xl p-5 border border-white/5">
              <p className="text-[#94A3B8] text-sm">Rooms</p>
              <p className="text-3xl font-bold text-white mt-1">
                {result.room_count}
              </p>
            </div>
            <div className="bg-[#1A2942] rounded-xl p-5 border border-white/5">
              <p className="text-[#94A3B8] text-sm">Total Area</p>
              <p className="text-3xl font-bold text-white mt-1">
                {formatNumber(result.total_area_m2, 0)}
                <span className="text-lg text-[#94A3B8] ml-1">m²</span>
              </p>
            </div>
            <div className="bg-[#1A2942] rounded-xl p-5 border border-white/5">
              <p className="text-[#94A3B8] text-sm">Counted Area</p>
              <p className="text-3xl font-bold text-[#00D4AA] mt-1">
                {formatNumber(result.total_counted_m2, 0)}
                <span className="text-lg text-[#00D4AA]/70 ml-1">m²</span>
              </p>
            </div>
            <div className="bg-[#1A2942] rounded-xl p-5 border border-white/5">
              <p className="text-[#94A3B8] text-sm">Blueprint Style</p>
              <p className="text-xl font-semibold text-white mt-1">
                {getStyleDisplayName(result.blueprint_style)}
              </p>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex items-center gap-2 border-b border-white/5 pb-4">
            <button
              onClick={() => setActiveTab("table")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                activeTab === "table"
                  ? "bg-[#00D4AA]/10 text-[#00D4AA]"
                  : "text-[#94A3B8] hover:text-white"
              }`}
            >
              <Table className="w-4 h-4" />
              Schedule
            </button>
            <button
              onClick={() => setActiveTab("charts")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                activeTab === "charts"
                  ? "bg-[#00D4AA]/10 text-[#00D4AA]"
                  : "text-[#94A3B8] hover:text-white"
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              Report
            </button>
          </div>

          {/* Table View */}
          {activeTab === "table" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Table */}
              <div className="lg:col-span-2 bg-[#1A2942] rounded-xl border border-white/5 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/5">
                        <th className="text-left text-xs font-medium text-[#64748B] uppercase tracking-wider px-4 py-3">
                          Room
                        </th>
                        <th className="text-left text-xs font-medium text-[#64748B] uppercase tracking-wider px-4 py-3">
                          Name
                        </th>
                        <th className="text-right text-xs font-medium text-[#64748B] uppercase tracking-wider px-4 py-3">
                          Area
                        </th>
                        <th className="text-right text-xs font-medium text-[#64748B] uppercase tracking-wider px-4 py-3">
                          Factor
                        </th>
                        <th className="text-right text-xs font-medium text-[#64748B] uppercase tracking-wider px-4 py-3">
                          Counted
                        </th>
                        <th className="text-center text-xs font-medium text-[#64748B] uppercase tracking-wider px-4 py-3">
                          Page
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {result.rooms.map((room, idx) => (
                        <tr
                          key={idx}
                          onClick={() => setSelectedRoom(room)}
                          className={`hover:bg-white/[0.02] cursor-pointer transition-colors ${
                            selectedRoom === room ? "bg-[#00D4AA]/5" : ""
                          } ${room.factor < 1 ? "bg-green-500/5" : ""}`}
                        >
                          <td className="px-4 py-3 text-sm font-mono text-[#00D4AA]">
                            {room.room_number}
                          </td>
                          <td className="px-4 py-3 text-sm text-white">
                            {room.room_name}
                          </td>
                          <td className="px-4 py-3 text-sm text-white text-right font-mono">
                            {formatNumber(room.area_m2)}
                          </td>
                          <td className="px-4 py-3 text-sm text-right">
                            {room.factor < 1 ? (
                              <span className="text-green-400">
                                {(room.factor * 100).toFixed(0)}%
                              </span>
                            ) : (
                              <span className="text-[#64748B]">100%</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-sm text-[#00D4AA] text-right font-mono font-medium">
                            {formatNumber(room.counted_m2)}
                          </td>
                          <td className="px-4 py-3 text-sm text-[#64748B] text-center">
                            {room.page}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Audit Panel */}
              <div className="bg-[#1A2942] rounded-xl border border-white/5 p-5">
                <h3 className="text-sm font-medium text-[#94A3B8] uppercase tracking-wider mb-4">
                  Audit Trail
                </h3>
                {selectedRoom ? (
                  <div className="space-y-4">
                    <div>
                      <p className="text-xs text-[#64748B]">Room Number</p>
                      <p className="text-white font-mono">
                        {selectedRoom.room_number}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-[#64748B]">Room Name</p>
                      <p className="text-white">{selectedRoom.room_name}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[#64748B]">Category</p>
                      <p className="text-white">
                        {getCategoryDisplayName(selectedRoom.category)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-[#64748B]">Area</p>
                      <p className="text-white font-mono">
                        {formatArea(selectedRoom.area_m2)}
                      </p>
                    </div>
                    <hr className="border-white/5" />
                    <div>
                      <p className="text-xs text-[#64748B] mb-2">Source Text</p>
                      <pre className="text-xs text-[#00D4AA] font-mono bg-[#0F1B2A] p-3 rounded-lg overflow-x-auto">
                        {selectedRoom.source_text}
                      </pre>
                    </div>
                    <div>
                      <p className="text-xs text-[#64748B]">Extraction Pattern</p>
                      <code className="text-xs text-[#F59E0B] font-mono">
                        {selectedRoom.extraction_pattern}
                      </code>
                    </div>
                    <div>
                      <p className="text-xs text-[#64748B]">Page</p>
                      <p className="text-white">{selectedRoom.page}</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-[#64748B]">
                    Select a room to view its audit trail
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Charts View */}
          {activeTab === "charts" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Category Bar Chart */}
              <div className="bg-[#1A2942] rounded-xl border border-white/5 p-6">
                <h3 className="text-lg font-semibold text-white mb-4">
                  Area by Category
                </h3>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={getCategoryChartData()}
                      layout="vertical"
                      margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="rgba(255,255,255,0.1)"
                      />
                      <XAxis
                        type="number"
                        tick={{ fill: "#94A3B8", fontSize: 12 }}
                        tickFormatter={(v) => `${v} m²`}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fill: "#94A3B8", fontSize: 12 }}
                        width={75}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#1A2942",
                          border: "1px solid rgba(255,255,255,0.1)",
                          borderRadius: "8px",
                        }}
                        labelStyle={{ color: "#fff" }}
                        formatter={(value) => [
                          `${formatNumber(Number(value) || 0)} m²`,
                          "Area",
                        ]}
                      />
                      <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                        {getCategoryChartData().map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Category Pie Chart */}
              <div className="bg-[#1A2942] rounded-xl border border-white/5 p-6">
                <h3 className="text-lg font-semibold text-white mb-4">
                  Distribution
                </h3>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={getCategoryChartData()}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {getCategoryChartData().map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#1A2942",
                          border: "1px solid rgba(255,255,255,0.1)",
                          borderRadius: "8px",
                        }}
                        formatter={(value) => [
                          `${formatNumber(Number(value) || 0)} m²`,
                          "Area",
                        ]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                {/* Legend */}
                <div className="grid grid-cols-2 gap-2 mt-4">
                  {getCategoryChartData()
                    .slice(0, 6)
                    .map((entry) => (
                      <div key={entry.name} className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: entry.color }}
                        />
                        <span className="text-xs text-[#94A3B8]">{entry.name}</span>
                      </div>
                    ))}
                </div>
              </div>

              {/* Page Distribution */}
              <div className="bg-[#1A2942] rounded-xl border border-white/5 p-6 lg:col-span-2">
                <h3 className="text-lg font-semibold text-white mb-4">
                  Area by Page
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={getPageChartData()}
                      margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="rgba(255,255,255,0.1)"
                      />
                      <XAxis
                        dataKey="name"
                        tick={{ fill: "#94A3B8", fontSize: 12 }}
                      />
                      <YAxis
                        tick={{ fill: "#94A3B8", fontSize: 12 }}
                        tickFormatter={(v) => `${v} m²`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#1A2942",
                          border: "1px solid rgba(255,255,255,0.1)",
                          borderRadius: "8px",
                        }}
                        formatter={(value) => [
                          `${formatNumber(Number(value) || 0)} m²`,
                          "Area",
                        ]}
                      />
                      <Bar dataKey="area" fill="#00D4AA" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="bg-[#F59E0B]/10 rounded-xl border border-[#F59E0B]/20 p-4">
              <h3 className="text-sm font-medium text-[#F59E0B] mb-2">
                Warnings
              </h3>
              <ul className="space-y-1">
                {result.warnings.map((warning, idx) => (
                  <li key={idx} className="text-sm text-[#F59E0B]/80">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

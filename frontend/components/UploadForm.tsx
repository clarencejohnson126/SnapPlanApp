"use client";

import { useState, useRef, FormEvent, ChangeEvent } from "react";

interface UploadFormProps {
  onSubmit: (params: { useSample: boolean; file: File | null }) => void;
  isLoading: boolean;
}

export default function UploadForm({ onSubmit, isLoading }: UploadFormProps) {
  const [useSample, setUseSample] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
    if (file) {
      setUseSample(false);
    }
  };

  const handleUseSampleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setUseSample(e.target.checked);
    if (e.target.checked) {
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ useSample, file: selectedFile });
  };

  return (
    <form onSubmit={handleSubmit} className="upload-form">
      <div className="form-section">
        <h2>Upload PDF</h2>
        <p className="form-description">
          Upload a Turliste (door schedule) PDF or use the sample file.
        </p>
      </div>

      <div className="form-group">
        <label htmlFor="file-upload" className="form-label">
          Select PDF file
        </label>
        <input
          id="file-upload"
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          disabled={useSample || isLoading}
          className="file-input"
        />
        {selectedFile && (
          <p className="file-name">Selected: {selectedFile.name}</p>
        )}
      </div>

      <div className="form-group checkbox-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={useSample}
            onChange={handleUseSampleChange}
            disabled={isLoading}
          />
          <span>Use sample Turliste (Tuerenliste_Bauteil_B_OG1.pdf)</span>
        </label>
      </div>

      <button
        type="submit"
        disabled={isLoading || (!useSample && !selectedFile)}
        className="submit-button"
      >
        {isLoading ? "Extracting..." : "Extract Schedule"}
      </button>
    </form>
  );
}

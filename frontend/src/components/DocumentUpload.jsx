import { useRef, useState } from "react";
import { uploadDocuments } from "../api/client";

const ACCEPTED = ".pdf,.docx,.txt,.md";

export default function DocumentUpload({ onUploaded }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);

  async function handleFiles(fileList) {
    const files = Array.from(fileList);
    if (files.length === 0) return;

    setIsUploading(true);
    setError(null);
    try {
      const result = await uploadDocuments(files);
      onUploaded(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-4 text-center text-sm transition-colors ${
          isDragging
            ? "border-brand-500 bg-brand-50"
            : "border-slate-300 hover:border-brand-400 hover:bg-slate-100"
        }`}
      >
        {isUploading ? (
          <span className="text-slate-500">Uploading & indexing…</span>
        ) : (
          <>
            <p className="font-medium text-slate-700">
              Drop files here or click to browse
            </p>
            <p className="mt-1 text-xs text-slate-400">
              PDF, DOCX, TXT, MD — up to 25MB each
            </p>
          </>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}

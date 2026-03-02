import { useRef, useState } from "react";
import { api } from "@/services/api";

interface DocumentUploadProps {
  onUploaded: () => void;
}

export function DocumentUpload({ onUploaded }: DocumentUploadProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState("");

  const handleUpload = async (file: File) => {
    setUploading(true);
    setStatus("Uploading...");
    try {
      const result = await api.uploadDocument(file);
      setStatus(`Uploaded: ${result.chunks_created} chunks created`);
      onUploaded();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-2">
      <input
        ref={fileRef}
        type="file"
        accept=".txt,.md,.pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleUpload(file);
        }}
      />
      <button
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
        className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg disabled:opacity-50 transition-colors"
      >
        {uploading ? "Uploading..." : "Upload Document"}
      </button>
      {status && <p className="text-xs text-gray-400">{status}</p>}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api } from "@/services/api";
import type { Document } from "@/types";
import { DocumentUpload } from "./DocumentUpload";

export function DocumentList() {
  const [documents, setDocuments] = useState<Document[]>([]);

  const loadDocuments = async () => {
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
    } catch {
      // Silently fail
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleDelete = async (id: string) => {
    await api.deleteDocument(id);
    loadDocuments();
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-3">
      <DocumentUpload onUploaded={loadDocuments} />
      {documents.length > 0 && (
        <ul className="space-y-1">
          {documents.map((doc) => (
            <li key={doc.id} className="flex items-center justify-between bg-gray-800 rounded-lg p-2">
              <div className="min-w-0 flex-1">
                <p className="text-sm text-white truncate">{doc.filename}</p>
                <p className="text-xs text-gray-400">{formatSize(doc.size_bytes)}</p>
              </div>
              <button
                onClick={() => handleDelete(doc.id)}
                className="ml-2 text-gray-500 hover:text-red-400 text-sm"
              >
                &times;
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

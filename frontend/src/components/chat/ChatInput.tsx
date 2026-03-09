import { useState, useEffect, useRef, type KeyboardEvent } from "react";
import { useChatStore } from "@/store/chatStore";
import { useSettingsStore } from "@/store/settingsStore";
import { api } from "@/services/api";
import { X, Paperclip, FileText, Image as ImageIcon, Cpu } from "lucide-react";

interface Attachment {
  id: string;
  type: "image" | "pdf";
  file: File;
  previewUrl?: string; // object URL for images
  extractedText?: string; // filled after PDF extraction
  uploadedPath?: string; // filled after image upload
  error?: string;
  isProcessing: boolean;
}

interface ChatInputProps {
  onSend: (message: string, images?: string[]) => void;
  disabled: boolean;
  isStreaming?: boolean;
  onStop?: () => void;
}

export function ChatInput({ onSend, disabled, isStreaming, onStop }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingInput = useChatStore((s) => s.pendingInput);

  const activeConversationId = useChatStore(s => s.activeConversationId);
  const conversations = useChatStore(s => s.conversations);
  const activeConv = conversations.find(c => c.id === activeConversationId);
  const localModels = useSettingsStore(s => s.localModels);

  // Model Capability Check
  const activeModel = localModels.find(m => m.name === activeConv?.model);
  const supportsVision = activeModel?.name.toLowerCase().includes("vision") ||
    activeModel?.name.toLowerCase().includes("vl") ||
    activeModel?.name.toLowerCase().includes("llava") ||
    activeModel?.name.toLowerCase().includes("minicpm") ||
    activeModel?.name.toLowerCase().includes("qwen");

  useEffect(() => {
    if (pendingInput !== null) {
      setInput(pendingInput);
      useChatStore.getState().setPendingInput(null);
      // Focus and move cursor to end
      setTimeout(() => {
        const el = textareaRef.current;
        if (el) {
          el.focus();
          el.style.height = "auto";
          el.style.height = Math.min(el.scrollHeight, 200) + "px";
        }
      }, 0);
    }
  }, [pendingInput]);

  const processFiles = async (files: FileList | File[]) => {
    setUploadError(null);
    const newAttachments: Attachment[] = [];

    for (const file of Array.from(files)) {
      if (file.type.startsWith("image/")) {
        // Warning if model doesn't support vision
        if (activeModel && !supportsVision) {
          setUploadError(`Model '${activeModel.name}' does not appear to support images.`);
          // We still allow attaching, but disable send later.
        }

        const previewUrl = URL.createObjectURL(file);
        const attachment: Attachment = {
          id: crypto.randomUUID(),
          type: "image",
          file,
          previewUrl,
          isProcessing: true,
        };
        newAttachments.push(attachment);

        // Upload immediately in background
        api.uploadImage(file).then(res => {
          setAttachments(prev => prev.map(a => a.id === attachment.id ? { ...a, uploadedPath: res.path, isProcessing: false } : a));
        }).catch(err => {
          setAttachments(prev => prev.map(a => a.id === attachment.id ? { ...a, error: err.message, isProcessing: false } : a));
        });

      } else if (file.type === "application/pdf") {
        const attachment: Attachment = {
          id: crypto.randomUUID(),
          type: "pdf",
          file,
          isProcessing: true,
        };
        newAttachments.push(attachment);

        // Extract text immediately
        api.extractPdf(file).then(res => {
          setAttachments(prev => prev.map(a => a.id === attachment.id ? { ...a, extractedText: res.text, isProcessing: false } : a));
        }).catch(err => {
          setAttachments(prev => prev.map(a => a.id === attachment.id ? { ...a, error: err.message, isProcessing: false } : a));
        });
      } else {
        setUploadError(`Unsupported file type: ${file.type}. Only Images and PDFs are allowed.`);
      }
    }

    setAttachments(prev => [...prev, ...newAttachments]);
    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    if (e.clipboardData.files && e.clipboardData.files.length > 0) {
      e.preventDefault();
      processFiles(e.clipboardData.files);
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments(prev => {
      const target = prev.find(a => a.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter(a => a.id !== id);
    });
    setUploadError(null);
  };

  const handleSend = () => {
    if (disabled || isProcessingAny) return;

    let finalMessage = input.trim();
    const imagePaths: string[] = [];

    for (const att of attachments) {
      if (att.type === "pdf" && att.extractedText) {
        finalMessage += `\n\n--- Attached Document: ${att.file.name} ---\n${att.extractedText}\n--- End Document ---\n`;
      } else if (att.type === "image" && att.uploadedPath) {
        imagePaths.push(att.uploadedPath);
      }
    }

    if (!finalMessage && imagePaths.length === 0) return;

    onSend(finalMessage, imagePaths.length > 0 ? imagePaths : undefined);
    setInput("");

    // Cleanup ObjectURLs to avoid memory leaks
    attachments.forEach(a => { if (a.previewUrl) URL.revokeObjectURL(a.previewUrl); });
    setAttachments([]);
  };

  const isProcessingAny = attachments.some(a => a.isProcessing);
  const hasImages = attachments.some(a => a.type === "image");
  const isSendDisabled = disabled ||
    isProcessingAny ||
    (!input.trim() && attachments.length === 0) ||
    (hasImages && !supportsVision && activeModel !== undefined);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-gray-800 p-4">
      {/* Attachments Preview Area */}
      {attachments.length > 0 && (
        <div className="flex gap-2 mb-3 overflow-x-auto pb-2 max-w-4xl mx-auto">
          {attachments.map((att) => (
            <div key={att.id} className="relative group shrink-0">
              {att.type === 'image' ? (
                <img src={att.previewUrl} alt="preview" className={`h-16 w-16 object-cover rounded-lg border flex-shrink-0 ${att.error ? 'border-red-500 opacity-50' : 'border-gray-700'}`} />
              ) : (
                <div className={`h-16 w-16 bg-gray-800 rounded-lg border flex flex-col items-center justify-center flex-shrink-0 ${att.error ? 'border-red-500' : 'border-gray-700'}`}>
                  <FileText className="w-6 h-6 text-gray-400 mb-1" />
                  <span className="text-[10px] text-gray-400 truncate w-full text-center px-1" title={att.file.name}>{att.file.name}</span>
                </div>
              )}
              {att.isProcessing && (
                <div className="absolute inset-0 bg-black/50 flex items-center justify-center rounded-lg">
                  <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                </div>
              )}
              <button
                onClick={() => removeAttachment(att.id)}
                className="absolute -top-2 -right-2 bg-gray-700 hover:bg-gray-600 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X className="w-3 h-3" />
              </button>
              {att.error && <p className="text-red-500 text-[10px] absolute -bottom-4 w-full text-center truncate">{att.error}</p>}
            </div>
          ))}
        </div>
      )}

      {/* Upload Error / Capability Warning */}
      {uploadError && (
        <div className="max-w-4xl mx-auto mb-2 text-red-400 text-sm">
          {uploadError}
        </div>
      )}
      {!supportsVision && hasImages && activeModel && (
        <div className="max-w-4xl mx-auto mb-2 text-yellow-500/90 text-sm">
          Warning: Model <b>{activeModel.name}</b> does not appear to support images. Send disabled.
        </div>
      )}

      <div className="flex gap-2 items-end max-w-4xl mx-auto relative">
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          multiple
          accept="image/*,application/pdf"
          onChange={(e) => e.target.files && processFiles(e.target.files)}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          className="p-3 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded-xl transition-colors disabled:opacity-50"
          title="Attach files (Images, PDFs)"
        >
          <Paperclip className="w-5 h-5" />
        </button>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="Type a message or paste files... (Shift+Enter for new line)"
          disabled={disabled}
          rows={1}
          className="flex-1 bg-gray-800 text-white border border-gray-700 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:border-blue-500 disabled:opacity-50 placeholder:text-gray-500"
          style={{ minHeight: "44px", maxHeight: "200px" }}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement;
            target.style.height = "auto";
            target.style.height = Math.min(target.scrollHeight, 200) + "px";
          }}
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="px-4 py-3 bg-red-600 hover:bg-red-500 text-white rounded-xl text-sm transition-colors"
          >
            Stop
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={isSendDisabled}
            className="px-4 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl text-sm transition-colors"
          >
            Send
          </button>
        )}
      </div>
      {activeConv?.model && (
        <div className="max-w-4xl mx-auto mt-1.5 flex items-center gap-1.5 px-1">
          <Cpu className="w-3 h-3 text-gray-500" />
          <span className="text-[11px] text-gray-500">{activeConv.model}</span>
        </div>
      )}
    </div>
  );
}

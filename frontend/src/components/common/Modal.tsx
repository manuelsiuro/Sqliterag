import { useEffect, useRef } from "react";
import ReactDOM from "react-dom";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export function Modal({ open, onClose, title, children }: ModalProps) {
  const backdropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return ReactDOM.createPortal(
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === backdropRef.current) onClose();
      }}
    >
      <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col animate-modal-content">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 shrink-0">
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl leading-none"
          >
            &times;
          </button>
        </div>
        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {children}
        </div>
      </div>
    </div>,
    document.body,
  );
}

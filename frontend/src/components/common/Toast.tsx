import { useEffect } from "react";

interface ToastProps {
  message: string;
  type?: "error" | "success" | "info";
  onClose: () => void;
  duration?: number;
}

export function Toast({ message, type = "error", onClose, duration = 5000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [onClose, duration]);

  const colors = {
    error: "bg-red-600",
    success: "bg-green-600",
    info: "bg-blue-600",
  };

  return (
    <div className={`fixed bottom-4 right-4 ${colors[type]} text-white px-4 py-3 rounded-lg shadow-lg z-50 max-w-sm`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm">{message}</p>
        <button onClick={onClose} className="text-white/80 hover:text-white text-lg leading-none">&times;</button>
      </div>
    </div>
  );
}

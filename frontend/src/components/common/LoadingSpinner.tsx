interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
}

export function LoadingSpinner({ size = "md" }: LoadingSpinnerProps) {
  const sizes = { sm: "h-4 w-4", md: "h-8 w-8", lg: "h-12 w-12" };
  return (
    <div className="flex items-center justify-center">
      <div className={`${sizes[size]} animate-spin rounded-full border-2 border-gray-600 border-t-blue-400`} />
    </div>
  );
}

import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
  rows?: number;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading data...',
  rows,
}) => {
  if (rows && rows > 0) {
    return (
      <div role="status" aria-live="polite" className="w-full space-y-3 p-4">
        <span className="sr-only">{message}</span>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="animate-pulse flex items-center space-x-4">
            <div className="h-4 bg-slate-200 rounded w-1/4"></div>
            <div className="h-4 bg-slate-200 rounded w-1/3"></div>
            <div className="h-4 bg-slate-200 rounded w-1/6"></div>
            <div className="h-4 bg-slate-200 rounded w-1/4"></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center p-12 text-slate-500 space-y-3"
    >
      <Loader2 className="w-8 h-8 animate-spin text-indigo-600" aria-hidden="true" />
      <span className="text-sm font-medium">{message}</span>
    </div>
  );
};


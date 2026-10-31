import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Something went wrong',
  message,
  onRetry,
}) => {
  return (
    <div
      role="alert"
      className="p-6 bg-red-50/70 border border-red-200 rounded-xl text-red-900 space-y-3"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" aria-hidden="true" />
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-red-950">{title}</h4>
          <p className="text-sm text-red-800 mt-1">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-100 text-red-900 hover:bg-red-200 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
              Try Again
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

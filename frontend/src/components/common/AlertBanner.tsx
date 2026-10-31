import React from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';

export type AlertType = 'success' | 'error' | 'warning' | 'info';

interface AlertBannerProps {
  type: AlertType;
  message: string;
  onClose?: () => void;
  className?: string;
}

export const AlertBanner: React.FC<AlertBannerProps> = ({
  type,
  message,
  onClose,
  className = '',
}) => {
  const styles = {
    success: 'bg-emerald-50 border-emerald-200 text-emerald-900',
    error: 'bg-red-50 border-red-200 text-red-900',
    warning: 'bg-amber-50 border-amber-200 text-amber-900',
    info: 'bg-blue-50 border-blue-200 text-blue-900',
  };

  const icons = {
    success: <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" aria-hidden="true" />,
    error: <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" aria-hidden="true" />,
    warning: <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" aria-hidden="true" />,
    info: <Info className="w-4 h-4 text-blue-600 flex-shrink-0" aria-hidden="true" />,
  };

  const role = type === 'error' ? 'alert' : 'status';
  const ariaLive = type === 'error' ? 'assertive' : 'polite';

  return (
    <div
      role={role}
      aria-live={ariaLive}
      className={`p-3 rounded-lg border text-sm flex items-center justify-between gap-3 ${styles[type]} ${className}`}
    >
      <div className="flex items-center gap-2.5">
        {icons[type]}
        <span>{message}</span>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-black/5 text-slate-500 hover:text-slate-800 transition"
          aria-label="Dismiss feedback"
        >
          <X className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      )}
    </div>
  );
};

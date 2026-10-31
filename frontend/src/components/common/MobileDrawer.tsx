import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { NavigationLinks } from '../NavigationLinks';

interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  currentTab: string;
  onSelectTab: (tab: string) => void;
}

export const MobileDrawer: React.FC<MobileDrawerProps> = ({
  isOpen,
  onClose,
  currentTab,
  onSelectTab,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Navigation Menu"
      className="fixed inset-0 z-50 md:hidden"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-over panel */}
      <div className="fixed inset-y-0 left-0 max-w-xs w-full bg-white shadow-xl flex flex-col justify-between p-4 z-10 overflow-y-auto">
        <div>
          {/* Header */}
          <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-200">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-base shadow-sm">
                B
              </div>
              <div>
                <span className="font-semibold text-slate-900 tracking-tight text-base">Brightloop</span>
                <span className="text-[11px] text-slate-500 block leading-none">Subscription OS</span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
              aria-label="Close navigation menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Links */}
          <nav aria-label="Mobile Navigation">
            <NavigationLinks
              currentTab={currentTab}
              onSelectTab={onSelectTab}
              onNavigate={onClose}
            />
          </nav>
        </div>

        <div className="pt-4 mt-6 border-t border-slate-200 text-xs text-slate-400">
          Brightloop v1.0 • Mobile Navigation
        </div>
      </div>
    </div>
  );
};


import React from 'react';
import { ChevronRight, Home } from 'lucide-react';

export interface BreadcrumbItem {
  label: string;
  tabKey?: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  onSelectTab?: (tabKey: string) => void;
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ items, onSelectTab }) => {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center text-xs text-slate-500 mb-2">
      <ol className="flex items-center space-x-1.5 flex-wrap">
        <li className="flex items-center">
          {onSelectTab ? (
            <button
              onClick={() => onSelectTab('dashboard')}
              className="flex items-center gap-1 text-slate-400 hover:text-slate-700 transition"
              aria-label="Home"
            >
              <Home className="w-3.5 h-3.5" aria-hidden="true" />
              <span className="sr-only">Home</span>
            </button>
          ) : (
            <span className="flex items-center text-slate-400" aria-label="Home">
              <Home className="w-3.5 h-3.5" aria-hidden="true" />
            </span>
          )}
        </li>
        {items.map((item, idx) => {
          const isLast = idx === items.length - 1;
          return (
            <li key={idx} className="flex items-center space-x-1.5">
              <ChevronRight className="w-3 h-3 text-slate-400 flex-shrink-0" aria-hidden="true" />
              {isLast || !item.tabKey || !onSelectTab ? (
                <span className={`font-medium ${isLast ? 'text-slate-800' : 'text-slate-500'}`} aria-current={isLast ? 'page' : undefined}>
                  {item.label}
                </span>
              ) : (
                <button
                  onClick={() => onSelectTab(item.tabKey!)}
                  className="hover:text-indigo-600 transition font-medium"
                >
                  {item.label}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};


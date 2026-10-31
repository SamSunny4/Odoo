import React from 'react';
import { NavigationLinks } from './NavigationLinks';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab }) => {
  return (
    <aside className="w-64 bg-white/90 backdrop-blur-xs border-r border-sky-100 hidden md:flex flex-col justify-between p-4 min-h-[calc(100vh-4rem)] shadow-2xs">
      <nav aria-label="Main Navigation">
        <NavigationLinks currentTab={currentTab} onSelectTab={onSelectTab} />
      </nav>
      <div className="pt-4 border-t border-sky-100/80 text-xs text-slate-400 flex items-center justify-between">
        <span className="font-medium text-slate-500">Brightloop v1.0</span>
        <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-sky-700 bg-sky-50 px-2 py-0.5 rounded-full border border-sky-200/60">
          <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 ring-2 ring-yellow-200 animate-pulse" />
          Active
        </span>
      </div>
    </aside>
  );
};

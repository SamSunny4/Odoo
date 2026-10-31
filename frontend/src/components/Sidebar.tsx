import React from 'react';
import { NavigationLinks } from './NavigationLinks';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab }) => {
  return (
    <aside className="w-64 bg-white border-r border-slate-200 hidden md:flex flex-col justify-between p-4 min-h-[calc(100vh-4rem)]">
      <nav aria-label="Main Navigation">
        <NavigationLinks currentTab={currentTab} onSelectTab={onSelectTab} />
      </nav>
      <div className="pt-4 border-t border-slate-200 text-xs text-slate-400">
        Brightloop v1.0 • Subscription OS
      </div>
    </aside>
  );
};

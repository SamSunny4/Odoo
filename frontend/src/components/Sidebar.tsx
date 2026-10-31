import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  Package,
  CalendarDays,
  FileText,
  Radio,
  Tag,
  Percent,
  Users,
  Building,
  Receipt,
  Sparkles,
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab }) => {
  const { user } = useAuth();

  const renderNavLinks = () => {
    if (user?.role === 'customer') {
      return (
        <div className="space-y-1">
          <div className="px-3 text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Customer Portal
          </div>
          <button
            onClick={() => onSelectTab('portal-subscriptions')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
              currentTab === 'portal-subscriptions'
                ? 'bg-indigo-50 text-indigo-700 font-semibold'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <CalendarDays className="w-4 h-4" />
            My Subscriptions
          </button>
          <button
            onClick={() => onSelectTab('portal-invoices')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
              currentTab === 'portal-invoices'
                ? 'bg-indigo-50 text-indigo-700 font-semibold'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <Receipt className="w-4 h-4" />
            My Invoices
          </button>
          <button
            onClick={() => onSelectTab('portal-profile')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
              currentTab === 'portal-profile'
                ? 'bg-indigo-50 text-indigo-700 font-semibold'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <Building className="w-4 h-4" />
            Company & Billing
          </button>
        </div>
      );
    }

    // Admin & Staff Navigation
    return (
      <div className="space-y-6">
        <div>
          <div className="px-3 text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Operations
          </div>
          <div className="space-y-1">
            <button
              onClick={() => onSelectTab('dashboard')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                currentTab === 'dashboard'
                  ? 'bg-indigo-50 text-indigo-700 font-semibold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              {user?.role === 'admin' ? 'Finance Dashboard' : 'Operations Queue'}
            </button>
            <button
              onClick={() => onSelectTab('subscriptions')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                currentTab === 'subscriptions'
                  ? 'bg-indigo-50 text-indigo-700 font-semibold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <CalendarDays className="w-4 h-4" />
              Subscriptions & Quotes
            </button>
            <button
              onClick={() => onSelectTab('invoices')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                currentTab === 'invoices'
                  ? 'bg-indigo-50 text-indigo-700 font-semibold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <FileText className="w-4 h-4" />
              Invoices & Payments
            </button>
            <button
              onClick={() => onSelectTab('control-tower')}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition ${
                currentTab === 'control-tower'
                  ? 'bg-indigo-50 text-indigo-700 font-semibold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <div className="flex items-center gap-3">
                <Radio className="w-4 h-4 text-indigo-600" />
                <span>Control Tower</span>
              </div>
              <span className="bg-indigo-100 text-indigo-700 text-[10px] px-1.5 py-0.5 rounded font-semibold flex items-center gap-0.5">
                <Sparkles className="w-2.5 h-2.5" />
                Standout
              </span>
            </button>
          </div>
        </div>

        <div>
          <div className="px-3 text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Catalog & Configuration
          </div>
          <div className="space-y-1">
            <button
              onClick={() => onSelectTab('catalog')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                currentTab === 'catalog'
                  ? 'bg-indigo-50 text-indigo-700 font-semibold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <Package className="w-4 h-4" />
              Products & Variants
            </button>

            {/* Admin-only configuration */}
            {user?.role === 'admin' && (
              <>
                <button
                  onClick={() => onSelectTab('plans')}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                    currentTab === 'plans'
                      ? 'bg-indigo-50 text-indigo-700 font-semibold'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <Tag className="w-4 h-4" />
                  Plans & Policies
                </button>
                <button
                  onClick={() => onSelectTab('discounts')}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                    currentTab === 'discounts'
                      ? 'bg-indigo-50 text-indigo-700 font-semibold'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <Percent className="w-4 h-4" />
                  Tax & Discount Rules
                </button>
                <button
                  onClick={() => onSelectTab('team')}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                    currentTab === 'team'
                      ? 'bg-indigo-50 text-indigo-700 font-semibold'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <Users className="w-4 h-4" />
                  Staff & Access
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <aside className="w-64 bg-white border-r border-slate-200 hidden md:flex flex-col justify-between p-4 min-h-[calc(100vh-4rem)]">
      <nav>{renderNavLinks()}</nav>
      <div className="pt-4 border-t border-slate-200 text-xs text-slate-400">
        Brightloop v1.0 • Phase 0 Scaffolding
      </div>
    </aside>
  );
};


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
  CreditCard,
  Sparkles,
  Mail,
} from 'lucide-react';

interface NavigationLinksProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  onNavigate?: () => void; // Called when an item is clicked (useful to close mobile drawer)
}

export const NavigationLinks: React.FC<NavigationLinksProps> = ({
  currentTab,
  onSelectTab,
  onNavigate,
}) => {
  const { user } = useAuth();

  const handleSelect = (tab: string) => {
    onSelectTab(tab);
    if (onNavigate) onNavigate();
  };

  if (user?.role === 'customer') {
    return (
      <div className="space-y-1">
        <div className="px-3 text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
          Customer Portal
        </div>
        <button
          onClick={() => handleSelect('portal-subscriptions')}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
            currentTab === 'portal-subscriptions'
              ? 'bg-indigo-50 text-indigo-700 font-semibold'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`}
        >
          <CalendarDays className="w-4 h-4 text-indigo-600" />
          My Subscriptions
        </button>
        <button
          onClick={() => handleSelect('portal-invoices')}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
            currentTab === 'portal-invoices'
              ? 'bg-indigo-50 text-indigo-700 font-semibold'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`}
        >
          <Receipt className="w-4 h-4 text-indigo-600" />
          My Invoices
        </button>
        <button
          onClick={() => handleSelect('portal-payments')}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
            currentTab === 'portal-payments'
              ? 'bg-indigo-50 text-indigo-700 font-semibold'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`}
        >
          <CreditCard className="w-4 h-4 text-indigo-600" />
          Payment History
        </button>
        <button
          onClick={() => handleSelect('portal-profile')}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
            currentTab === 'portal-profile'
              ? 'bg-indigo-50 text-indigo-700 font-semibold'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`}
        >
          <Building className="w-4 h-4 text-indigo-600" />
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
            onClick={() => handleSelect('dashboard')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
              currentTab === 'dashboard'
                ? 'bg-indigo-50 text-indigo-700 font-semibold'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <LayoutDashboard className="w-4 h-4 text-indigo-600" />
            {user?.role === 'admin' ? 'Finance Dashboard' : 'Operations Queue'}
          </button>
          <button
            onClick={() => handleSelect('subscriptions')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
              currentTab === 'subscriptions'
                ? 'bg-indigo-50 text-indigo-700 font-semibold'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <CalendarDays className="w-4 h-4 text-indigo-600" />
            Subscriptions & Quotes
          </button>
          <button
            onClick={() => handleSelect('invoices')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
              currentTab === 'invoices'
                ? 'bg-indigo-50 text-indigo-700 font-semibold'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <FileText className="w-4 h-4 text-indigo-600" />
            Invoices & Payments
          </button>
          <button
            onClick={() => handleSelect('communications')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
              currentTab === 'communications'
                ? 'bg-indigo-50 text-indigo-700 font-semibold'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <Mail className="w-4 h-4 text-indigo-600" />
            Communications
          </button>
          <button
            onClick={() => handleSelect('control-tower')}
            className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition ${
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
            onClick={() => handleSelect('catalog')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
              currentTab === 'catalog'
                ? 'bg-indigo-50 text-indigo-700 font-semibold'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <Package className="w-4 h-4 text-indigo-600" />
            Products & Variants
          </button>

          {/* Admin-only configuration */}
          {user?.role === 'admin' && (
            <>
              <button
                onClick={() => handleSelect('plans')}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                  currentTab === 'plans'
                    ? 'bg-indigo-50 text-indigo-700 font-semibold'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <Tag className="w-4 h-4 text-indigo-600" />
                Plans & Policies
              </button>
              <button
                onClick={() => handleSelect('discounts')}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                  currentTab === 'discounts'
                    ? 'bg-indigo-50 text-indigo-700 font-semibold'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <Percent className="w-4 h-4 text-indigo-600" />
                Tax & Discount Rules
              </button>
              <button
                onClick={() => handleSelect('team')}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                  currentTab === 'team'
                    ? 'bg-indigo-50 text-indigo-700 font-semibold'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <Users className="w-4 h-4 text-indigo-600" />
                Staff & Access
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};


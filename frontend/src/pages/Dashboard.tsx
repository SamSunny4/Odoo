import React from 'react';
import { useAuth } from '../context/AuthContext';
import { TrendingUp, Users, CalendarCheck, AlertTriangle, ArrowUpRight, DollarSign } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {isAdmin ? 'Finance & Revenue Operations' : 'Staff Operations Dashboard'}
          </h1>
          <p className="text-sm text-slate-500">
            {isAdmin
              ? 'Real-time overview of recurring revenue, collections, and active subscriber health.'
              : 'Daily workflow queue: quotes to confirm, billing runs, and customer inquiries.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
            ● System Operational
          </span>
          <span className="text-xs text-slate-400">Response time: ~42ms</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {isAdmin ? (
          <>
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Monthly Recurring Revenue</span>
                <DollarSign className="w-4 h-4 text-indigo-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">$28,450.00</div>
              <div className="flex items-center gap-1 text-xs text-emerald-600 mt-2 font-medium">
                <ArrowUpRight className="w-3.5 h-3.5" />
                <span>+12.4% from last month</span>
              </div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Active Subscriptions</span>
                <Users className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">342</div>
              <div className="text-xs text-slate-500 mt-2">Across 210 customer accounts</div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Cash Collected (MTD)</span>
                <TrendingUp className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">$21,800.00</div>
              <div className="text-xs text-slate-500 mt-2">76% of invoiced total</div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Overdue Balance</span>
                <AlertTriangle className="w-4 h-4 text-amber-600" />
              </div>
              <div className="text-2xl font-bold text-amber-600">$3,420.00</div>
              <div className="text-xs text-slate-500 mt-2">8 invoices pending follow-up</div>
            </div>
          </>
        ) : (
          <>
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Pending Quotes</span>
                <CalendarCheck className="w-4 h-4 text-indigo-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">14</div>
              <div className="text-xs text-slate-500 mt-2">Awaiting customer acceptance</div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Renewals Due This Week</span>
                <CalendarCheck className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">28</div>
              <div className="text-xs text-slate-500 mt-2">Next billing cycle queued</div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Unallocated Payments</span>
                <TrendingUp className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">3</div>
              <div className="text-xs text-slate-500 mt-2">Needs manual match</div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">Overdue Chasing Queue</span>
                <AlertTriangle className="w-4 h-4 text-amber-600" />
              </div>
              <div className="text-2xl font-bold text-amber-600">8 Invoices</div>
              <div className="text-xs text-slate-500 mt-2">Oldest: 18 days overdue</div>
            </div>
          </>
        )}
      </div>

      {/* Standout Feature Callout */}
      <div className="bg-gradient-to-r from-indigo-900 to-indigo-800 rounded-xl p-6 text-white shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/30 text-indigo-200 mb-2">
            ⭐ Standout Workflow
          </div>
          <h2 className="text-xl font-bold">Billing Control Tower Preview Ready</h2>
          <p className="text-indigo-200 text-sm mt-1 max-w-xl">
            Simulate and audit upcoming recurring billing batches before generating real invoices. Inspect variances, catch expired discounts, and prevent duplicate billing.
          </p>
        </div>
        <div className="shrink-0">
          <span className="text-xs bg-white text-indigo-900 font-semibold px-4 py-2 rounded-lg shadow-sm">
            Phase 0 Data Models Ready
          </span>
        </div>
      </div>
    </div>
  );
};


import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import type { DashboardSummary, MoneyValue } from '../services/api';
import { AlertTriangle, ArrowUpRight, CalendarCheck, DollarSign, TrendingUp, Users } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    api.getDashboardSummary()
      .then((result: DashboardSummary) => { if (current) setSummary(result); })
      .catch((reason: unknown) => { if (current) setError(reason instanceof Error ? reason.message : 'Could not load the dashboard.'); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, []);

  const money = (value: MoneyValue | null | undefined) => value === null || value === undefined
    ? '—'
    : new Intl.NumberFormat(undefined, { style: 'currency', currency: summary?.currency || 'USD' }).format(Number(value));
  const metricCard = (label: string, value: string, detail: string, Icon: typeof DollarSign, color: string) => (
    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
      <div className="flex items-center justify-between text-slate-500 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
      <div className="text-2xl font-bold text-slate-900">{loading ? '…' : value}</div>
      <div className="text-xs text-slate-500 mt-2">{detail}</div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{isAdmin ? 'Finance & Revenue Operations' : 'Staff Operations Dashboard'}</h1>
          <p className="text-sm text-slate-500">{isAdmin ? 'Current recurring revenue, collections, and overdue balances.' : 'Quotes, renewals, and invoice follow-up at a glance.'}</p>
        </div>
        <span className="text-xs text-slate-500">{summary ? `Reporting currency: ${summary.currency}` : 'Summary unavailable'}</span>
      </div>

      {error && <div role="alert" className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {isAdmin ? <>
          {metricCard('Monthly Recurring Revenue', money(summary?.monthly_recurring_revenue), 'Active subscription run rate, before tax', DollarSign, 'text-indigo-600')}
          {metricCard('Active Subscriptions', String(summary?.active_subscription_count ?? '—'), 'Current active contracts', Users, 'text-blue-600')}
          {metricCard('Cash Collected (MTD)', money(summary?.cash_collected_mtd), `Invoiced this month: ${money(summary?.invoiced_mtd)}`, TrendingUp, 'text-emerald-600')}
          {metricCard('Overdue Balance', money(summary?.overdue_balance), `${summary?.overdue_invoice_count ?? '—'} invoices need follow-up`, AlertTriangle, 'text-amber-600')}
        </> : <>
          {metricCard('Pending Quotes', String(summary?.pending_quotes_count ?? '—'), 'Awaiting confirmation', CalendarCheck, 'text-indigo-600')}
          {metricCard('Renewals Due This Week', String(summary?.renewals_due_7d_count ?? '—'), 'Active subscriptions due in 7 days', CalendarCheck, 'text-blue-600')}
          {metricCard('Active Subscriptions', String(summary?.active_subscription_count ?? '—'), 'Current active contracts', Users, 'text-emerald-600')}
          {metricCard('Overdue Invoices', String(summary?.overdue_invoice_count ?? '—'), 'Open invoices past their due date', AlertTriangle, 'text-amber-600')}
        </>}
      </div>

      <div className="bg-gradient-to-r from-indigo-900 to-indigo-800 rounded-xl p-6 text-white shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/30 text-indigo-200 mb-2"><ArrowUpRight className="w-3 h-3" /> Billing review</div>
          <h2 className="text-xl font-bold">Billing Control Tower</h2>
          <p className="text-indigo-200 text-sm mt-1 max-w-xl">Preview due renewals, review exceptions, and approve a saved billing run before invoices are created.</p>
        </div>
        <div className="shrink-0 text-xs bg-white text-indigo-900 font-semibold px-4 py-2 rounded-lg shadow-sm">{summary ? `${summary.renewals_due_7d_count} renewals due in 7 days` : loading ? 'Loading summary…' : 'Summary unavailable'}</div>
      </div>
    </div>
  );
};

import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import type { DashboardSummary, MoneyValue } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { ErrorState } from '../components/common/ErrorState';
import { AlertTriangle, CalendarCheck, DollarSign, TrendingUp, Users, RefreshCw } from 'lucide-react';

interface DashboardProps {
  onNavigate?: (tabKey: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onNavigate }) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getDashboardSummary();
      setSummary(result);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Could not load the dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const money = (value: MoneyValue | null | undefined) =>
    value === null || value === undefined
      ? '—'
      : new Intl.NumberFormat(undefined, {
          style: 'currency',
          currency: summary?.currency || 'USD',
        }).format(Number(value));

  const metricCard = (
    label: string,
    value: string,
    detail: string,
    Icon: typeof DollarSign,
    color: string
  ) => (
    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between text-slate-500 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
          <Icon className={`w-4 h-4 ${color}`} />
        </div>
        <div className="text-2xl font-bold text-slate-900">{loading ? '…' : value}</div>
      </div>
      <div className="text-xs text-slate-500 mt-2">{detail}</div>
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={isAdmin ? 'Finance & Revenue Operations' : 'Staff Operations Dashboard'}
        subtitle={
          isAdmin
            ? 'Current recurring revenue run rate, cash collections, and overdue balances.'
            : 'Operational queue: pending quotes, upcoming renewals, and invoice collections at a glance.'
        }
        breadcrumbs={[
          { label: 'Brightloop', tabKey: 'dashboard' },
          { label: 'Operations' },
          { label: isAdmin ? 'Finance Dashboard' : 'Operations Queue' },
        ]}
        onSelectTab={onNavigate}
        badge={
          <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-slate-100 text-slate-600">
            {summary ? `Reporting Currency: ${summary.currency}` : 'Connecting...'}
          </span>
        }
        actions={
          <button
            onClick={fetchSummary}
            className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
            title="Refresh Dashboard"
            aria-label="Refresh Dashboard metrics"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        }
      />

      {error && <ErrorState message={error} onRetry={fetchSummary} />}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {isAdmin ? (
          <>
            {metricCard(
              'Monthly Recurring Revenue',
              money(summary?.monthly_recurring_revenue),
              'Active subscription run rate, before tax',
              DollarSign,
              'text-indigo-600'
            )}
            {metricCard(
              'Active Subscriptions',
              String(summary?.active_subscription_count ?? '—'),
              'Current active contracts',
              Users,
              'text-blue-600'
            )}
            {metricCard(
              'Cash Collected (MTD)',
              money(summary?.cash_collected_mtd),
              `Invoiced this month: ${money(summary?.invoiced_mtd)}`,
              TrendingUp,
              'text-emerald-600'
            )}
            {metricCard(
              'Overdue Balance',
              money(summary?.overdue_balance),
              `${summary?.overdue_invoice_count ?? '—'} invoices need follow-up`,
              AlertTriangle,
              'text-amber-600'
            )}
          </>
        ) : (
          <>
            {metricCard(
              'Pending Quotes',
              String(summary?.pending_quotes_count ?? '—'),
              'Awaiting confirmation',
              CalendarCheck,
              'text-indigo-600'
            )}
            {metricCard(
              'Renewals Due (7 Days)',
              String(summary?.renewals_due_7d_count ?? '—'),
              'Active contracts nearing renewal',
              CalendarCheck,
              'text-blue-600'
            )}
            {metricCard(
              'Active Subscriptions',
              String(summary?.active_subscription_count ?? '—'),
              'Current operational contracts',
              Users,
              'text-emerald-600'
            )}
            {metricCard(
              'Overdue Invoices',
              String(summary?.overdue_invoice_count ?? '—'),
              'Open invoices requiring outreach',
              AlertTriangle,
              'text-amber-600'
            )}
          </>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <h3 className="text-base font-bold text-slate-900 mb-2">Operations Guide & Cadence</h3>
        <p className="text-sm text-slate-600 leading-relaxed max-w-3xl">
          Brightloop processes subscriptions on recurring anchor dates. Use the{' '}
          <strong className="text-indigo-700">Control Tower</strong> to preview and inspect batch billing runs before commits, ensuring no duplicate invoices or unhandled anomalies occur.
        </p>
      </div>
    </div>
  );
};

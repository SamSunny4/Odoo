import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  api,
  CustomerAccountApiItem,
  PlanApiItem,
  DrillDownReport,
} from '../services/api';
import type { DashboardSummary, MoneyValue } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { PaginationControls } from '../components/common/PaginationControls';
import {
  AlertTriangle,
  CalendarCheck,
  DollarSign,
  TrendingUp,
  Users,
  RefreshCw,
  Download,
  Info,
  Radio,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Receipt,
} from 'lucide-react';

interface DashboardProps {
  onNavigate?: (tabKey: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onNavigate }) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  // Reporting Period State
  const [period, setPeriod] = useState<string>('this_month');

  // Dashboard Metrics State
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showDefinitions, setShowDefinitions] = useState<boolean>(false);

  // Drill-Down Ledger State
  const [activeMetric, setActiveMetric] = useState<string>('invoiced');
  const [drillData, setDrillData] = useState<DrillDownReport | null>(null);
  const [drillLoading, setDrillLoading] = useState<boolean>(false);
  const [drillPage, setDrillPage] = useState<number>(1);
  const [drillPageSize, setDrillPageSize] = useState<number>(10);
  const [drillSearch, setDrillSearch] = useState<string>('');
  const [drillPlanId, setDrillPlanId] = useState<string>('');
  const [drillCustomerId, setDrillCustomerId] = useState<string>('');

  // Lookup Options State
  const [plans, setPlans] = useState<PlanApiItem[]>([]);
  const [customers, setCustomers] = useState<CustomerAccountApiItem[]>([]);

  // 1. Fetch Dashboard Metrics
  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getDashboardSummary({ period });
      setSummary(result);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Could not load the dashboard.');
    } finally {
      setLoading(false);
    }
  }, [period]);

  // 2. Fetch Drill-Down Ledger Items
  const fetchDrillDown = useCallback(async () => {
    if (!isAdmin) return;
    setDrillLoading(true);
    try {
      const result = await api.getDrillDownReport({
        metric: activeMetric,
        period,
        plan_id: drillPlanId || undefined,
        customer_account_id: drillCustomerId || undefined,
        search: drillSearch || undefined,
        page: drillPage,
        page_size: drillPageSize,
      });
      setDrillData(result);
    } catch (err: unknown) {
      console.error('Failed to load drill-down records:', err);
    } finally {
      setDrillLoading(false);
    }
  }, [isAdmin, activeMetric, period, drillPlanId, drillCustomerId, drillSearch, drillPage, drillPageSize]);

  // 3. Load Filters (Plans & Customers)
  useEffect(() => {
    if (!isAdmin) return;
    api.getPlans().then(setPlans).catch(() => {});
    api.getCustomerAccounts().then(setCustomers).catch(() => {});
  }, [isAdmin]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    if (isAdmin) {
      fetchDrillDown();
    }
  }, [isAdmin, fetchDrillDown]);

  const money = (value: MoneyValue | null | undefined) =>
    value === null || value === undefined
      ? '—'
      : new Intl.NumberFormat(undefined, {
          style: 'currency',
          currency: summary?.currency || 'USD',
        }).format(Number(value));

  const handleCardClick = (metricKey: string) => {
    if (!isAdmin) return;
    setActiveMetric(metricKey);
    setDrillPage(1);
  };

  const handleExportCsv = () => {
    const exportUrl = api.getReportExportUrl({
      metric: activeMetric,
      period,
      plan_id: drillPlanId || undefined,
      customer_account_id: drillCustomerId || undefined,
      search: drillSearch || undefined,
    });
    window.open(exportUrl, '_blank');
  };

  const metricCard = (
    label: string,
    value: string,
    detail: string,
    Icon: typeof DollarSign,
    color: string,
    metricKey?: string,
    isActive?: boolean
  ) => (
    <div
      onClick={() => metricKey && handleCardClick(metricKey)}
      className={`bg-white p-5 rounded-xl border transition flex flex-col justify-between ${
        metricKey ? 'cursor-pointer hover:shadow-md' : ''
      } ${
        isActive
          ? 'border-indigo-600 ring-2 ring-indigo-500/20 shadow-xs'
          : 'border-slate-200 shadow-xs hover:border-slate-300'
      }`}
    >
      <div>
        <div className="flex items-center justify-between text-slate-500 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
          <Icon className={`w-4 h-4 ${color}`} />
        </div>
        <div className="text-2xl font-bold font-mono text-slate-900">{loading ? '…' : value}</div>
      </div>
      <div className="text-xs text-slate-500 mt-2 flex items-center justify-between">
        <span>{detail}</span>
        {metricKey && isAdmin && (
          <span className="text-[11px] font-semibold text-indigo-600 hover:underline inline-flex items-center gap-0.5">
            Drill down <ArrowRight className="w-3 h-3" />
          </span>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={isAdmin ? 'Finance & Revenue Operations' : 'Staff Operations Dashboard'}
        subtitle={
          isAdmin
            ? 'Traceable reconciliation: recurring run rates, invoiced demands, and cash collections.'
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
          <div className="flex items-center gap-2">
            {isAdmin && (
              <button
                onClick={handleExportCsv}
                className="px-3 py-2 border border-slate-200 rounded-lg text-slate-700 bg-white hover:bg-slate-50 text-xs sm:text-sm font-semibold flex items-center gap-1.5 shadow-2xs transition"
                title="Export current financial dataset to CSV"
              >
                <Download className="w-4 h-4 text-slate-500" />
                Export CSV
              </button>
            )}
            <button
              onClick={() => {
                fetchSummary();
                if (isAdmin) fetchDrillDown();
              }}
              className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
              title="Refresh Dashboard"
              aria-label="Refresh Dashboard metrics"
            >
              <RefreshCw className={`w-4 h-4 ${loading || drillLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={fetchSummary} />}

      {/* Period Filter Bar (Admin) */}
      {isAdmin && (
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <span className="text-xs font-semibold uppercase text-slate-400 tracking-wider mr-2">Period:</span>
            {[
              { label: 'This Month', value: 'this_month' },
              { label: 'Last Month', value: 'last_month' },
              { label: 'This Quarter', value: 'this_quarter' },
              { label: 'This Year', value: 'this_year' },
              { label: 'All Time', value: 'all_time' },
            ].map((p) => (
              <button
                key={p.value}
                onClick={() => {
                  setPeriod(p.value);
                  setDrillPage(1);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                  period === p.value
                    ? 'bg-indigo-600 text-white shadow-2xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-500">
            {summary?.period_start && summary?.period_end && (
              <span className="font-mono bg-slate-50 px-2 py-1 rounded border border-slate-200">
                Range: {summary.period_start} → {summary.period_end}
              </span>
            )}
            <button
              onClick={() => setShowDefinitions(!showDefinitions)}
              className="text-indigo-600 hover:underline flex items-center gap-1 font-medium"
            >
              <Info className="w-3.5 h-3.5" />
              {showDefinitions ? 'Hide Definitions' : 'View Accounting Rules'}
            </button>
          </div>
        </div>
      )}

      {/* Accounting Definitions Callout */}
      {showDefinitions && isAdmin && (
        <div className="p-4 bg-indigo-50/70 border border-indigo-200 rounded-xl text-xs space-y-2 text-indigo-900 animate-in fade-in">
          <div className="font-bold text-sm text-indigo-950 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-indigo-600" />
            Brightloop Accounting Invariants & Rule Visibility
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            <div className="p-2.5 bg-white rounded-lg border border-indigo-100">
              <strong className="text-slate-900">Invoiced Revenue (Billing Accrual):</strong> Total value of official
              financial invoices confirmed or paid within the chosen date range. Represents legally issued demand.
            </div>
            <div className="p-2.5 bg-white rounded-lg border border-indigo-100">
              <strong className="text-slate-900">Cash Collected (Cash Receipts):</strong> Actual cash remittances
              received against invoices in this date window, minus any payment reversals or refunds.
            </div>
            <div className="p-2.5 bg-white rounded-lg border border-indigo-100">
              <strong className="text-slate-900">Monthly Recurring Revenue (MRR):</strong> Normalized monthly run
              rate of active subscription contracts, calculated before tax and discounts.
            </div>
            <div className="p-2.5 bg-white rounded-lg border border-indigo-100">
              <strong className="text-slate-900">Outstanding Balance:</strong> Cumulative uncollected balance across all
              confirmed customer invoices currently in the system.
            </div>
          </div>
        </div>
      )}

      {/* Summary Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {isAdmin ? (
          <>
            {metricCard(
              'Monthly Recurring Revenue',
              money(summary?.monthly_recurring_revenue),
              'Active contract run rate (MRR)',
              DollarSign,
              'text-indigo-600',
              'mrr',
              activeMetric === 'mrr'
            )}
            {metricCard(
              'Invoiced Revenue',
              money(summary?.invoiced_revenue ?? summary?.invoiced_mtd),
              `Billing demand in period`,
              Receipt,
              'text-blue-600',
              'invoiced',
              activeMetric === 'invoiced'
            )}
            {metricCard(
              'Cash Collected',
              money(summary?.cash_collected ?? summary?.cash_collected_mtd),
              `Net cash receipts received`,
              TrendingUp,
              'text-emerald-600',
              'collected',
              activeMetric === 'collected'
            )}
            {metricCard(
              'Overdue Balance',
              money(summary?.overdue_balance),
              `${summary?.overdue_invoice_count ?? '—'} invoices past credit terms`,
              AlertTriangle,
              'text-amber-600',
              'overdue',
              activeMetric === 'overdue'
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

      {/* Standout Billing Control Tower Teaser Banner */}
      <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-slate-900 rounded-xl p-5 text-white flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-indigo-400" />
            <span className="font-bold text-base tracking-tight">Billing Control Tower (Standout Feature)</span>
            <span className="bg-indigo-500/30 text-indigo-200 text-[10px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1 border border-indigo-400/20">
              <Sparkles className="w-2.5 h-2.5" /> Standout
            </span>
          </div>
          <p className="text-xs text-indigo-200 max-w-2xl leading-relaxed">
            Inspect upcoming billing batches before committing demands. Automatically detects price anomalies, expired discounts, variance against prior invoices, and prevents duplicate billing.
          </p>
        </div>
        <button
          onClick={() => onNavigate && onNavigate('control-tower')}
          className="px-4 py-2.5 bg-white text-indigo-900 hover:bg-indigo-50 font-semibold text-xs sm:text-sm rounded-lg shadow-sm transition shrink-0 flex items-center gap-1.5 self-start sm:self-auto"
        >
          Open Control Tower
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* ADMIN DRILL-DOWN LEDGER (Phase 8 Requirement) */}
      {isAdmin && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden space-y-4 p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <span>Drill-Down Reconciliation Ledger</span>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 uppercase font-semibold">
                  {activeMetric.replace('_', ' ')}
                </span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Every summary metric is traced to exact underlying financial records without spreadsheets.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleExportCsv}
                className="px-3 py-1.5 border border-slate-200 text-slate-700 bg-white hover:bg-slate-50 text-xs font-semibold rounded-lg flex items-center gap-1 shadow-2xs transition"
              >
                <Download className="w-3.5 h-3.5 text-slate-500" />
                Export Ledger CSV
              </button>
            </div>
          </div>

          {/* Drill-Down Filter Toolbar */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            {/* Metric Switcher Dropdown */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Metric View</label>
              <select
                value={activeMetric}
                onChange={(e) => {
                  setActiveMetric(e.target.value);
                  setDrillPage(1);
                }}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white"
              >
                <option value="invoiced">Invoiced Revenue (Demands)</option>
                <option value="collected">Cash Collections (Receipts)</option>
                <option value="outstanding">Outstanding Balances</option>
                <option value="overdue">Overdue Balances</option>
                <option value="subscriptions">Active Contracts (MRR)</option>
                <option value="all">All Documents</option>
              </select>
            </div>

            {/* Plan Filter */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Filter by Plan</label>
              <select
                value={drillPlanId}
                onChange={(e) => {
                  setDrillPlanId(e.target.value);
                  setDrillPage(1);
                }}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white"
              >
                <option value="">All Plans</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Customer Filter */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Filter by Customer</label>
              <select
                value={drillCustomerId}
                onChange={(e) => {
                  setDrillCustomerId(e.target.value);
                  setDrillPage(1);
                }}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white"
              >
                <option value="">All Customers</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.company_name}
                  </option>
                ))}
              </select>
            </div>

            {/* Search */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Search</label>
              <input
                type="text"
                placeholder="Search reference # or name..."
                value={drillSearch}
                onChange={(e) => {
                  setDrillSearch(e.target.value);
                  setDrillPage(1);
                }}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg"
              />
            </div>
          </div>

          {/* Drill-Down Table */}
          {drillLoading ? (
            <LoadingState message="Filtering and resolving financial drill-down records..." rows={5} />
          ) : !drillData || drillData.items.length === 0 ? (
            <EmptyState
              title="No records matching filter"
              description="No financial transactions or contracts found for this metric and date range."
            />
          ) : (
            <>
              <div className="overflow-x-auto border border-slate-200 rounded-xl">
                <table className="w-full text-left border-collapse text-xs min-w-[750px]">
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider border-b border-slate-200">
                      <th className="py-2.5 px-3">Reference #</th>
                      <th className="py-2.5 px-3">Customer</th>
                      <th className="py-2.5 px-3">Plan / Category</th>
                      <th className="py-2.5 px-3">Date</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3 text-right">Amount</th>
                      <th className="py-2.5 px-3 text-right">Paid</th>
                      <th className="py-2.5 px-3 text-right">Balance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {drillData.items.map((row) => (
                      <tr key={row.id} className="hover:bg-slate-50/70 transition">
                        <td className="py-2.5 px-3 font-mono font-semibold text-indigo-700">
                          {row.reference_number}
                        </td>
                        <td className="py-2.5 px-3 font-medium text-slate-900">{row.customer_name}</td>
                        <td className="py-2.5 px-3 text-slate-600">{row.plan_name || row.metric_category}</td>
                        <td className="py-2.5 px-3 text-slate-500 font-mono">{row.date}</td>
                        <td className="py-2.5 px-3">
                          <span className="capitalize px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700">
                            {row.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-900">
                          ${Number(row.amount).toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-emerald-600">
                          ${Number(row.paid_amount || 0).toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono font-semibold text-red-600">
                          ${Number(row.balance || 0).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 text-xs">
                <div className="text-slate-600 font-medium">
                  Showing {drillData.items.length} of {drillData.total_items} records • Filtered Total:{' '}
                  <span className="font-bold font-mono text-slate-900">${Number(drillData.total_amount).toFixed(2)}</span>
                </div>
                <PaginationControls
                  page={drillPage}
                  totalPages={drillData.total_pages}
                  total={drillData.total_items}
                  pageSize={drillPageSize}
                  onPageChange={setDrillPage}
                  onPageSizeChange={(sz) => {
                    setDrillPageSize(sz);
                    setDrillPage(1);
                  }}
                />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

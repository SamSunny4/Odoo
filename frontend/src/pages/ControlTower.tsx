import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api, BillingRunSummaryApiItem } from '../services/api';
import type { MoneyValue } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { AlertBanner } from '../components/common/AlertBanner';
import { ErrorState } from '../components/common/ErrorState';
import { Modal } from '../components/common/Modal';
import {
  CheckCircle2,
  Lock,
  RefreshCw,
  Layers,
  AlertTriangle,
  History,
  RotateCw,
  Ban,
  Play,
  ShieldCheck,
  Check,
  Download,
} from 'lucide-react';

interface ControlTowerItem {
  id: string;
  subscription_id: string;
  subscription_number: string;
  customer_name: string;
  plan_name: string;
  expected_subtotal: MoneyValue;
  expected_tax_amount: MoneyValue;
  expected_discount_amount: MoneyValue;
  expected_total_amount: MoneyValue;
  prior_invoice_total?: MoneyValue | null;
  variance_amount?: MoneyValue | null;
  variance_reasons: string[];
  warnings: string[];
  status: string;
  skip_reason?: string | null;
}

interface PreviewResponse {
  billing_run_id: string;
  billing_period_start: string;
  billing_period_end: string;
  total_projected_amount: MoneyValue;
  flagged_count: number;
  items: ControlTowerItem[];
}

interface ControlTowerProps {
  onNavigate?: (tabKey: string) => void;
}

type TabType = 'preview' | 'exceptions' | 'history';

export const ControlTower: React.FC<ControlTowerProps> = ({ onNavigate }) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [activeTab, setActiveTab] = useState<TabType>('preview');

  // Preview Run State
  const [items, setItems] = useState<ControlTowerItem[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [period, setPeriod] = useState({ start: '', end: '' });
  const [totalProjected, setTotalProjected] = useState(0);
  const [flaggedCount, setFlaggedCount] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [batchSize, setBatchSize] = useState<number>(50);
  const [committed, setCommitted] = useState(false);
  const [commitMessage, setCommitMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [committing, setCommitting] = useState(false);

  // Exceptions Tab State
  const [exceptions, setExceptions] = useState<ControlTowerItem[]>([]);
  const [exceptionsLoading, setExceptionsLoading] = useState(false);

  // Historical Runs State
  const [historicalRuns, setHistoricalRuns] = useState<BillingRunSummaryApiItem[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);

  // Skip Modal State
  const [skipModalItem, setSkipModalItem] = useState<ControlTowerItem | null>(null);
  const [skipReason, setSkipReason] = useState<string>('');
  const [skipSubmitting, setSkipSubmitting] = useState<boolean>(false);

  // Auto-bill State
  const [autoBilling, setAutoBilling] = useState<boolean>(false);

  const cleanItems = useMemo(() => items.filter((item) => item.status === 'pending'), [items]);

  const fetchPreview = async (size = batchSize) => {
    setLoading(true);
    setError(null);
    setCommitMessage(null);
    setCommitted(false);
    setSelectedIds([]);
    try {
      const data = (await api.getControlTowerPreview(size)) as PreviewResponse;
      setRunId(data.billing_run_id);
      setItems(data.items);
      setPeriod({ start: data.billing_period_start, end: data.billing_period_end });
      setTotalProjected(Number(data.total_projected_amount));
      setFlaggedCount(data.flagged_count);
      setSelectedIds(data.items.filter((i) => i.status === 'pending').map((i) => i.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not generate billing preview.');
    } finally {
      setLoading(false);
    }
  };

  const fetchExceptions = async () => {
    setExceptionsLoading(true);
    try {
      const data = (await api.getControlTowerExceptions()) as ControlTowerItem[];
      setExceptions(data);
    } catch {
      setExceptions([]);
    } finally {
      setExceptionsLoading(false);
    }
  };

  const fetchHistory = async () => {
    setRunsLoading(true);
    try {
      const data = await api.getControlTowerRuns(25);
      setHistoricalRuns(data);
    } catch {
      setHistoricalRuns([]);
    } finally {
      setRunsLoading(false);
    }
  };

  useEffect(() => {
    void fetchPreview();
  }, []);

  useEffect(() => {
    if (activeTab === 'exceptions') {
      void fetchExceptions();
    } else if (activeTab === 'history') {
      void fetchHistory();
    }
  }, [activeTab]);

  const toggleItem = (itemId: string) => {
    if (selectedIds.includes(itemId)) {
      setSelectedIds(selectedIds.filter((id) => id !== itemId));
      return;
    }
    if (selectedIds.length >= 50) {
      setError('Manual batch generation is limited to 50 invoices at a time. Commit a smaller preview batch.');
      return;
    }
    setSelectedIds([...selectedIds, itemId]);
  };

  const handleSelectAllClean = () => {
    const firstFifty = cleanItems.slice(0, 50).map((item) => item.id);
    if (selectedIds.length === firstFifty.length && firstFifty.every((id) => selectedIds.includes(id))) {
      setSelectedIds([]);
    } else {
      setSelectedIds(firstFifty);
    }
  };

  const handleCommit = async () => {
    if (!isAdmin || !runId || selectedIds.length === 0) return;
    setCommitting(true);
    setError(null);
    setCommitMessage(null);
    try {
      const result = await api.commitControlTowerPreview(runId, selectedIds);
      setCommitted(true);
      setCommitMessage(
        `${result.invoices_created_count} invoices created for ₹${Number(
          result.total_invoiced_amount
        ).toFixed(2)}. ${result.failed_count} items need retry.`
      );
      await fetchPreview();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Could not commit the selected invoices.'
      );
    } finally {
      setCommitting(false);
    }
  };

  const handleRetryItem = async (itemId: string) => {
    try {
      const res = await api.retryControlTowerItem(itemId);
      setCommitMessage(`Re-evaluation complete: ${res.message}`);
      await fetchPreview();
      if (activeTab === 'exceptions') {
        await fetchExceptions();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to re-evaluate item.');
    }
  };

  const handleOpenSkip = (item: ControlTowerItem) => {
    setSkipModalItem(item);
    setSkipReason('Manual hold by billing operator');
  };

  const handleSkipSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!skipModalItem || !skipReason.trim()) return;

    setSkipSubmitting(true);
    try {
      await api.skipControlTowerItem(skipModalItem.id, skipReason.trim());
      setSkipModalItem(null);
      await fetchPreview();
      if (activeTab === 'exceptions') {
        await fetchExceptions();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to skip item.');
    } finally {
      setSkipSubmitting(false);
    }
  };

  const handleTriggerAutoBill = async () => {
    setAutoBilling(true);
    setError(null);
    try {
      const res = await api.triggerAutoBill();
      setCommitMessage(`Automated billing was queued in the background (job ${res.task_id}).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Automated billing trigger failed.');
    } finally {
      setAutoBilling(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Billing Control Tower"
        subtitle="Preview upcoming recurring charges, review flagged issues before invoicing, and resolve exceptions."
        breadcrumbs={[
          { label: 'Brightloop', tabKey: 'dashboard' },
          { label: 'Operations', tabKey: 'dashboard' },
          { label: 'Control Tower' },
        ]}
        onSelectTab={onNavigate}
        actions={
          <div className="flex items-center gap-2">
            {isAdmin && (
              <button
                onClick={handleTriggerAutoBill}
                disabled={autoBilling || loading || committing}
                className="px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 flex items-center gap-1.5 shadow-2xs transition"
                title="Run automated recurring billing in background"
              >
                <Play className={`w-3.5 h-3.5 text-indigo-600 ${autoBilling ? 'animate-pulse' : ''}`} />
                {autoBilling ? 'Running Scheduler…' : 'Run Scheduled Billing'}
              </button>
            )}
            <button
              onClick={() => void fetchPreview()}
              disabled={loading || committing}
              className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-50 transition"
              title="Create a fresh preview"
              aria-label="Refresh preview"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            {isAdmin ? (
              <button
                onClick={() => void handleCommit()}
                disabled={
                  committed || loading || committing || !runId || selectedIds.length === 0
                }
                className="px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed flex items-center gap-2 transition"
              >
                <CheckCircle2 className="w-4 h-4" />
                {committing
                  ? 'Generating Invoices…'
                  : committed
                  ? 'Invoices Generated'
                  : `Generate Invoices (${selectedIds.length})`}
              </button>
            ) : (
              <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 text-amber-800 px-3 py-1.5 rounded-lg text-xs font-medium">
                <Lock className="w-3.5 h-3.5" /> Staff can preview batches; an administrator must generate invoices.
              </div>
            )}
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={() => fetchPreview()} />}
      {commitMessage && (
        <AlertBanner
          type="success"
          message={commitMessage}
          onClose={() => setCommitMessage(null)}
        />
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200 flex gap-6 text-sm font-medium">
        <button
          onClick={() => setActiveTab('preview')}
          className={`pb-3 px-1 border-b-2 font-semibold flex items-center gap-2 transition ${
            activeTab === 'preview'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Layers className="w-4 h-4" />
          Batch Preview
          {items.length > 0 && (
            <span className="bg-slate-100 text-slate-700 text-xs px-2 py-0.5 rounded-full">
              {items.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('exceptions')}
          className={`pb-3 px-1 border-b-2 font-semibold flex items-center gap-2 transition ${
            activeTab === 'exceptions'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <AlertTriangle className="w-4 h-4" />
          Issues & Exceptions
          {flaggedCount > 0 && (
            <span className="bg-yellow-400 text-slate-950 text-xs px-2 py-0.5 rounded-full font-extrabold shadow-2xs">
              {flaggedCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('history')}
          className={`pb-3 px-1 border-b-2 font-semibold flex items-center gap-2 transition ${
            activeTab === 'history'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <History className="w-4 h-4" />
          Billing Run History
        </button>
      </div>

      {activeTab === 'preview' && (
        <>
          {/* Metrics bar */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 grid grid-cols-2 sm:grid-cols-4 gap-4 text-center sm:text-left shadow-xs">
            <div>
              <div className="text-xs text-slate-400 font-semibold uppercase">Billing Period</div>
              <div className="text-base font-bold text-slate-800">
                {period.start || '—'} – {period.end || '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-400 font-semibold uppercase">
                Subscriptions to Bill
              </div>
              <div className="text-base font-bold text-slate-800">{items.length}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 font-semibold uppercase">Projected Batch Total</div>
              <div className="text-base font-bold text-indigo-600">₹{totalProjected.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 font-semibold uppercase">Flagged Items</div>
              <div
                className={`text-base font-bold ${
                  flaggedCount ? 'text-amber-600' : 'text-emerald-600'
                }`}
              >
                {flaggedCount}
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 bg-slate-50/50">
              <div className="flex items-center gap-3">
                <h2 className="font-semibold text-slate-800 text-sm">Upcoming Invoices to Review</h2>
                <button
                  onClick={handleSelectAllClean}
                  disabled={committed || !isAdmin || cleanItems.length === 0}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold disabled:opacity-50"
                >
                  {cleanItems.length > 0 && selectedIds.length === Math.min(cleanItems.length, 50) &&
                  cleanItems.slice(0, 50).every((item) => selectedIds.includes(item.id))
                    ? 'Deselect First 50'
                    : `Select Ready Invoices (Up to 50) (${Math.min(cleanItems.length, 50)})`}
                </button>
                <span className="text-xs text-slate-500">Manual batch generation is limited to 50 invoices at a time.</span>
              </div>
              <div className="flex items-center gap-2">
                <label htmlFor="batch-size" className="text-xs font-semibold text-slate-500">
                  Batch Size:
                </label>
                <select
                  id="batch-size"
                  value={batchSize}
                  onChange={(e) => {
                    const sz = Number(e.target.value);
                    setBatchSize(sz);
                    void fetchPreview(sz);
                  }}
                  className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white text-slate-700"
                >
                  <option value={25}>25 subscriptions</option>
                  <option value={50}>50 subscriptions</option>
                </select>
                <span className="text-xs text-slate-400 ml-2">
                  Preview Run: {runId ? runId.slice(0, 8) : '—'}
                </span>
                {runId && (
                  <button
                    onClick={async () => {
                      try {
                        await api.downloadControlTowerRunCsv(runId);
                      } catch (err: unknown) {
                        const msg = err instanceof Error ? err.message : 'Failed to export run CSV';
                        setError(msg);
                      }
                    }}
                    className="px-2.5 py-1 border border-slate-200 text-slate-700 bg-white hover:bg-slate-50 text-xs font-semibold rounded-md shadow-2xs flex items-center gap-1 transition ml-2"
                    title="Export preview batch to CSV"
                  >
                    <Download className="w-3.5 h-3.5 text-slate-500" />
                    Export CSV
                  </button>
                )}
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm min-w-[850px]">
                <thead>
                  <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase border-b border-slate-200">
                    <th className="py-3 px-4">Select</th>
                    <th className="py-3 px-4">Subscription</th>
                    <th className="py-3 px-4">Customer & Plan</th>
                    <th className="py-3 px-4 text-right">Subtotal & Tax</th>
                    <th className="py-3 px-4 text-right">Invoice Amount</th>
                    <th className="py-3 px-4">Change vs Prior Invoice</th>
                    <th className="py-3 px-4">Review Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {items.map((item) => {
                    const clean = item.status === 'pending';
                    const isFlagged = item.status === 'flagged' || item.warnings.length > 0;
                    return (
                      <tr key={item.id} className="hover:bg-slate-50/60 transition">
                        <td className="py-3 px-4">
                          <input
                            type="checkbox"
                            aria-label={`Select ${item.subscription_number}`}
                            checked={selectedIds.includes(item.id)}
                            disabled={!clean || committed || !isAdmin}
                            onChange={() => toggleItem(item.id)}
                            className="rounded text-indigo-600 focus:ring-indigo-500"
                          />
                        </td>
                        <td className="py-3 px-4 font-mono font-medium text-xs text-indigo-700">
                          {item.subscription_number}
                        </td>
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-900">{item.customer_name}</div>
                          <div className="text-xs text-slate-500">{item.plan_name}</div>
                        </td>
                        <td className="py-3 px-4 text-right text-xs font-mono text-slate-600">
                          ₹{Number(item.expected_subtotal).toFixed(2)} − ₹
                          {Number(item.expected_discount_amount).toFixed(2)} + ₹
                          {Number(item.expected_tax_amount).toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-semibold font-mono text-slate-900">
                          ₹{Number(item.expected_total_amount).toFixed(2)}
                        </td>
                        <td className="py-3 px-4">
                          {Number(item.variance_amount || 0) !== 0 ? (
                            <div className="text-xs font-semibold text-amber-700">
                              {Number(item.variance_amount) > 0 ? '+' : ''}
                              ${Number(item.variance_amount).toFixed(2)}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">Stable</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {isFlagged ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                              <AlertTriangle className="w-3 h-3" /> Flagged
                            </span>
                          ) : item.status === 'invoiced' ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                              <Check className="w-3 h-3" /> Invoiced
                            </span>
                          ) : item.status === 'skipped' ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-700">
                              Skipped
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700">
                              <ShieldCheck className="w-3 h-3" /> Clean
                            </span>
                          )}
                          {item.warnings.length > 0 && (
                            <div className="text-[11px] text-amber-700 mt-0.5">
                              {item.warnings.join(', ')}
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {isFlagged && (
                              <button
                                onClick={() => handleRetryItem(item.id)}
                                className="px-2 py-1 text-xs font-semibold rounded bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition flex items-center gap-1"
                                title="Re-evaluate pricing / tax rules"
                              >
                                <RotateCw className="w-3 h-3" /> Retry
                              </button>
                            )}
                            {item.status !== 'invoiced' && item.status !== 'skipped' && (
                              <button
                                onClick={() => handleOpenSkip(item)}
                                className="px-2 py-1 text-xs font-semibold rounded bg-slate-100 text-slate-600 hover:bg-slate-200 transition flex items-center gap-1"
                                title="Skip for this run"
                              >
                                <Ban className="w-3 h-3" /> Skip
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {activeTab === 'exceptions' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-4 border-b border-slate-200 flex items-center justify-between">
            <h2 className="font-semibold text-slate-800 text-sm">Billing Exceptions &amp; Failed Attempts</h2>
            <button
              onClick={fetchExceptions}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh Exceptions
            </button>
          </div>

          {exceptionsLoading ? (
            <div className="p-6 text-center text-sm text-slate-500">Loading exception queue...</div>
          ) : exceptions.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">
              <ShieldCheck className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
              Zero exceptions found. All due subscriptions are currently clean and eligible for automated billing.
            </div>
          ) : (
            <div className="divide-y divide-slate-200">
              {exceptions.map((ex) => (
                <div key={ex.id} className="p-4 flex flex-wrap items-center justify-between gap-4 hover:bg-slate-50 transition">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-indigo-700">{ex.subscription_number}</span>
                      <span className="text-sm font-semibold text-slate-900">{ex.customer_name}</span>
                      <span className="text-xs text-slate-500">({ex.plan_name})</span>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      {ex.warnings.map((w, idx) => (
                        <span key={idx} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">
                          <AlertTriangle className="w-3 h-3" /> {w}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-xs font-semibold text-slate-900 font-mono">
                        ${Number(ex.expected_total_amount).toFixed(2)}
                      </div>
                      <div className="text-[11px] text-slate-400">Projected Demand</div>
                    </div>
                    <button
                      onClick={() => handleRetryItem(ex.id)}
                      className="px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 text-xs font-semibold hover:bg-indigo-100 flex items-center gap-1.5 transition"
                    >
                      <RotateCw className="w-3.5 h-3.5" /> {ex.status === 'failed' ? 'Retry billing' : 'Re-evaluate'}
                    </button>
                    <button
                      onClick={() => handleOpenSkip(ex)}
                      className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 text-xs font-semibold hover:bg-slate-200 flex items-center gap-1.5 transition"
                    >
                      <Ban className="w-3.5 h-3.5" /> Skip
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'history' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-4 border-b border-slate-200 flex items-center justify-between">
            <h2 className="font-semibold text-slate-800 text-sm">Historical Billing Runs</h2>
            <button
              onClick={fetchHistory}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh Runs
            </button>
          </div>

          {runsLoading ? (
            <div className="p-6 text-center text-sm text-slate-500">Loading historical runs...</div>
          ) : historicalRuns.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">No previous billing runs recorded.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm min-w-[900px]">
                <thead>
                  <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase border-b border-slate-200">
                    <th className="py-3 px-4">Run Date</th>
                    <th className="py-3 px-4">Billing Period</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Evaluated</th>
                    <th className="py-3 px-4 text-right">Invoices Created</th>
                    <th className="py-3 px-4 text-right">Skipped</th>
                    <th className="py-3 px-4 text-right">Flagged</th>
                    <th className="py-3 px-4 text-right">Failed</th>
                    <th className="py-3 px-4 text-right">Projected Run</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {historicalRuns.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50/60 transition">
                      <td className="py-3 px-4 font-mono text-xs text-slate-900">{r.run_date}</td>
                      <td className="py-3 px-4 text-xs text-slate-600">
                        {r.billing_period_start} &rarr; {r.billing_period_end}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${
                            r.status === 'committed'
                              ? 'bg-emerald-100 text-emerald-800'
                              : r.status === 'preview'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-medium">{r.total_evaluated}</td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-emerald-700">
                        {r.invoices_created_count}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-500">{r.skipped_count}</td>
                      <td className="py-3 px-4 text-right font-mono text-amber-600 font-semibold">
                        {r.flagged_count}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-red-600 font-semibold">
                        {r.failed_count}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                        ${Number(r.total_amount_projected).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Skip Item Modal */}
      <Modal
        isOpen={skipModalItem !== null}
        onClose={() => setSkipModalItem(null)}
        title="Skip Subscription for this Billing Run"
        subtitle={
          skipModalItem
            ? `${skipModalItem.subscription_number} • ${skipModalItem.customer_name}`
            : undefined
        }
      >
        {skipModalItem && (
          <form onSubmit={handleSkipSubmit} className="space-y-4">
            <p className="text-xs text-slate-600">
              Skipping excludes this subscription from the current billing run without advancing its next billing date.
            </p>
            <div>
              <label htmlFor="skip-reason" className="block text-xs font-semibold text-slate-700 mb-1">
                Skip Reason *
              </label>
              <input
                id="skip-reason"
                type="text"
                required
                value={skipReason}
                onChange={(e) => setSkipReason(e.target.value)}
                placeholder="e.g. Account executive requested temporary hold..."
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setSkipModalItem(null)}
                className="px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={skipSubmitting || !skipReason.trim()}
                className="px-4 py-2 text-xs sm:text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 transition"
              >
                {skipSubmitting ? 'Skipping...' : 'Confirm Skip'}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
};

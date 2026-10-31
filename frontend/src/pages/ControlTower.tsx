import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import type { MoneyValue } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { AlertBanner } from '../components/common/AlertBanner';
import { ErrorState } from '../components/common/ErrorState';
import { AlertCircle, CheckCircle2, Lock, RefreshCw, Sparkles } from 'lucide-react';

interface ControlTowerItem {
  id: string;
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
}

interface PreviewResponse {
  billing_run_id: string;
  billing_period_start: string;
  billing_period_end: string;
  total_projected_amount: MoneyValue;
  flagged_count: number;
  items: ControlTowerItem[];
}

export const ControlTower: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [items, setItems] = useState<ControlTowerItem[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [period, setPeriod] = useState({ start: '', end: '' });
  const [totalProjected, setTotalProjected] = useState(0);
  const [flaggedCount, setFlaggedCount] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [committed, setCommitted] = useState(false);
  const [commitMessage, setCommitMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [committing, setCommitting] = useState(false);

  const cleanItems = useMemo(() => items.filter((item) => item.status === 'pending'), [items]);

  const fetchPreview = async () => {
    setLoading(true);
    setError(null);
    setCommitMessage(null);
    setCommitted(false);
    setSelectedIds([]);
    try {
      const data = (await api.getControlTowerPreview()) as PreviewResponse;
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

  useEffect(() => {
    void fetchPreview();
  }, []);

  const toggleItem = (itemId: string) => {
    setSelectedIds((current) =>
      current.includes(itemId) ? current.filter((id) => id !== itemId) : [...current, itemId]
    );
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
        `${result.invoices_created_count} invoices created for $${Number(
          result.total_invoiced_amount
        ).toFixed(2)}.`
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Could not commit the selected invoices.'
      );
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Billing Control Tower"
        subtitle="Inspect calculated invoices, review variances, and select clean items for billing."
        breadcrumbs={[
          { label: 'Brightloop' },
          { label: 'Operations' },
          { label: 'Control Tower' },
        ]}
        badge={
          <span className="bg-indigo-100 text-indigo-700 text-xs px-2 py-0.5 rounded-full font-semibold flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> Standout Feature
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
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
                  ? 'Committing…'
                  : committed
                  ? 'Run Committed'
                  : `Commit Selected (${selectedIds.length})`}
              </button>
            ) : (
              <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 text-amber-800 px-3 py-1.5 rounded-lg text-xs font-medium">
                <Lock className="w-3.5 h-3.5" /> Staff can preview; an admin must commit.
              </div>
            )}
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={fetchPreview} />}
      {commitMessage && (
        <AlertBanner
          type="success"
          message={`Billing run committed. ${commitMessage}`}
          onClose={() => setCommitMessage(null)}
        />
      )}

      <div className="bg-white p-4 rounded-xl border border-slate-200 grid grid-cols-2 sm:grid-cols-4 gap-4 text-center sm:text-left shadow-xs">
        <div>
          <div className="text-xs text-slate-400 font-semibold uppercase">Billing Period</div>
          <div className="text-base font-bold text-slate-800">
            {period.start || '—'} – {period.end || '—'}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-400 font-semibold uppercase">
            Subscriptions Evaluated
          </div>
          <div className="text-base font-bold text-slate-800">{items.length}</div>
        </div>
        <div>
          <div className="text-xs text-slate-400 font-semibold uppercase">Projected Run</div>
          <div className="text-base font-bold text-indigo-600">${totalProjected.toFixed(2)}</div>
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

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between gap-3">
          <h2 className="font-semibold text-slate-800 text-sm">Billing preview items</h2>
          <span className="text-xs text-slate-400">
            Preview run: {runId ? runId.slice(0, 8) : '—'}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm min-w-[750px]">
            <thead>
              <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase border-b border-slate-200">
                <th className="py-3 px-4">Select</th>
                <th className="py-3 px-4">Subscription</th>
                <th className="py-3 px-4">Customer & Plan</th>
                <th className="py-3 px-4 text-right">Subtotal − Discount + Tax</th>
                <th className="py-3 px-4 text-right">Total</th>
                <th className="py-3 px-4">Prior Variance</th>
                <th className="py-3 px-4">Review</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {items.map((item) => {
                const clean = item.status === 'pending';
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
                      ${Number(item.expected_subtotal).toFixed(2)} − $
                      {Number(item.expected_discount_amount).toFixed(2)} + $
                      {Number(item.expected_tax_amount).toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right font-semibold font-mono">
                      ${Number(item.expected_total_amount).toFixed(2)}
                    </td>
                    <td className="py-3 px-4">
                      {Number(item.variance_amount || 0) !== 0 ? (
                        <div>
                          <span className="text-xs font-semibold text-amber-700">
                            Δ ${Number(item.variance_amount).toFixed(2)}
                          </span>
                          <div className="text-[11px] text-slate-500">
                            {item.variance_reasons.join(', ')}
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">Stable</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {item.warnings.length ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                          <AlertCircle className="w-3 h-3" />
                          {item.warnings.join(' ')}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">
                          <CheckCircle2 className="w-3 h-3" />
                          Clean
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-sm text-slate-500">
                    No subscriptions are due for billing today.
                  </td>
                </tr>
              )}
              {loading && (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-sm text-slate-500">
                    Preparing billing preview…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {!committed && cleanItems.length > 0 && (
          <div className="px-4 py-3 border-t border-slate-100 text-xs text-slate-500">
            Only selected clean items are billed. Flagged items remain unbilled for investigation.
          </div>
        )}
      </div>
    </div>
  );
};

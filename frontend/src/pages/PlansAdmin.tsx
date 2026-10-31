import React, { useState, useEffect, useCallback } from 'react';
import { api, PlanApiItem, CreatePlanPayload, UpdatePlanPayload } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { AlertBanner } from '../components/common/AlertBanner';
import {
  Calendar,
  Plus,
  RefreshCw,
  Edit2,
  Trash2,
  X,
  CheckCircle2,
  XCircle,
  PauseCircle,
  Clock,
  ShieldAlert,
} from 'lucide-react';

interface PlansAdminProps {
  onNavigate?: (tabKey: string) => void;
}

export const PlansAdmin: React.FC<PlansAdminProps> = ({ onNavigate }) => {
  const [plans, setPlans] = useState<PlanApiItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Modal State
  const [showModal, setShowModal] = useState<boolean>(false);
  const [editingPlan, setEditingPlan] = useState<PlanApiItem | null>(null);
  const [form, setForm] = useState<{
    name: string;
    cadence: string;
    base_price: string;
    min_quantity: number;
    available_from: string;
    available_to: string;
    auto_close_on_expiry: boolean;
    allow_early_close: boolean;
    allow_pause: boolean;
    allow_renewal: boolean;
  }>({
    name: '',
    cadence: 'monthly',
    base_price: '',
    min_quantity: 1,
    available_from: '',
    available_to: '',
    auto_close_on_expiry: false,
    allow_early_close: true,
    allow_pause: true,
    allow_renewal: true,
  });
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchPlans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getPlans();
      setPlans(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load plans.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  const openCreateModal = () => {
    setEditingPlan(null);
    setForm({
      name: '',
      cadence: 'monthly',
      base_price: '',
      min_quantity: 1,
      available_from: '',
      available_to: '',
      auto_close_on_expiry: false,
      allow_early_close: true,
      allow_pause: true,
      allow_renewal: true,
    });
    setFormError(null);
    setShowModal(true);
  };

  const openEditModal = (p: PlanApiItem) => {
    setEditingPlan(p);
    setForm({
      name: p.name,
      cadence: p.cadence,
      base_price: String(p.base_price),
      min_quantity: p.min_quantity,
      available_from: p.available_from || '',
      available_to: p.available_to || '',
      auto_close_on_expiry: p.auto_close_on_expiry,
      allow_early_close: p.allow_early_close,
      allow_pause: p.allow_pause,
      allow_renewal: p.allow_renewal,
    });
    setFormError(null);
    setShowModal(true);
  };

  const handleSavePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const price = parseFloat(form.base_price);
    if (isNaN(price) || price < 0) {
      setFormError('Base price must be a valid non-negative number.');
      return;
    }

    if (form.available_from && form.available_to && form.available_from > form.available_to) {
      setFormError('Availability start date cannot be after end date.');
      return;
    }

    if (!form.allow_renewal && !form.auto_close_on_expiry) {
      setFormError(
        'Incompatible policies: When renewals are disabled, the plan must enable automatic close upon expiry.'
      );
      return;
    }

    setSubmitting(true);
    try {
      if (editingPlan) {
        const payload: UpdatePlanPayload = {
          name: form.name.trim(),
          cadence: form.cadence,
          base_price: form.base_price,
          min_quantity: form.min_quantity,
          available_from: form.available_from || undefined,
          available_to: form.available_to || undefined,
          auto_close_on_expiry: form.auto_close_on_expiry,
          allow_early_close: form.allow_early_close,
          allow_pause: form.allow_pause,
          allow_renewal: form.allow_renewal,
        };
        await api.updatePlan(editingPlan.id, payload);
        setFeedback({ type: 'success', message: `Plan "${form.name}" updated successfully.` });
      } else {
        const payload: CreatePlanPayload = {
          name: form.name.trim(),
          cadence: form.cadence,
          base_price: form.base_price,
          min_quantity: form.min_quantity,
          available_from: form.available_from || undefined,
          available_to: form.available_to || undefined,
          auto_close_on_expiry: form.auto_close_on_expiry,
          allow_early_close: form.allow_early_close,
          allow_pause: form.allow_pause,
          allow_renewal: form.allow_renewal,
        };
        await api.createPlan(payload);
        setFeedback({ type: 'success', message: `Plan "${form.name}" created successfully.` });
      }

      setShowModal(false);
      fetchPlans();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save plan.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleArchivePlan = async (p: PlanApiItem) => {
    if (!window.confirm(`Archive plan "${p.name}"? It will no longer be available for new customer subscriptions.`)) {
      return;
    }
    try {
      await api.archivePlan(p.id);
      setFeedback({ type: 'success', message: `Plan "${p.name}" archived successfully.` });
      fetchPlans();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to archive plan.' });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Subscription Plans Administration"
        subtitle="Configure billing cadences, base pricing, availability dates, and lifecycle policies (pause, early-close, automatic renewal)."
        breadcrumbs={[
          { label: 'Brightloop', tabKey: 'dashboard' },
          { label: 'Catalog & Configuration', tabKey: 'catalog' },
          { label: 'Subscription Plans' },
        ]}
        onSelectTab={onNavigate}
        badge={
          <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-800">
            Admin Controlled
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={fetchPlans}
              className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
              title="Refresh plans"
              aria-label="Refresh plans list"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={openCreateModal}
              className="px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-xs sm:text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-1.5 shadow-xs"
            >
              <Plus className="w-4 h-4" />
              <span>Create Plan</span>
            </button>
          </div>
        }
      />

      {feedback && (
        <AlertBanner
          type={feedback.type}
          message={feedback.message}
          onClose={() => setFeedback(null)}
        />
      )}

      {error && <ErrorState message={error} onRetry={fetchPlans} />}

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <LoadingState message="Loading subscription plans..." rows={4} />
        ) : plans.length === 0 ? (
          <EmptyState
            title="No subscription plans configured"
            description="Create your first recurring cadence plan to start enrolling subscribers."
            action={{ label: 'Create Plan', onClick: openCreateModal }}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm min-w-[850px]">
              <thead>
                <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                  <th className="py-3 px-4">Plan Name & Cadence</th>
                  <th className="py-3 px-4 text-right">Base Price</th>
                  <th className="py-3 px-4 text-center">Min Qty</th>
                  <th className="py-3 px-4">Availability Window</th>
                  <th className="py-3 px-4">Lifecycle Policies</th>
                  <th className="py-3 px-4 text-center">Status</th>
                  <th className="py-3 px-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {plans.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/60 transition">
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-900">{p.name}</div>
                      <div className="mt-1">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100 capitalize">
                          <Clock className="w-3 h-3 text-indigo-500" />
                          {p.cadence}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900">
                      ${Number(p.base_price).toFixed(2)}
                      <span className="text-xs text-slate-400 font-normal"> / {p.cadence}</span>
                    </td>
                    <td className="py-3.5 px-4 text-center font-mono text-slate-700">
                      {p.min_quantity}
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-600">
                      {p.available_from || p.available_to ? (
                        <div className="flex items-center gap-1 text-slate-700">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span>{p.available_from || 'Open'}</span>
                          <span className="text-slate-400">→</span>
                          <span>{p.available_to || 'Indefinite'}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Always Available</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-wrap gap-1 text-xs">
                        {p.allow_pause && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[11px] font-medium border border-blue-100">
                            <PauseCircle className="w-3 h-3 text-blue-500" /> Pause
                          </span>
                        )}
                        {p.allow_early_close && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 text-[11px] font-medium border border-amber-100">
                            <ShieldAlert className="w-3 h-3 text-amber-500" /> Early Close
                          </span>
                        )}
                        {p.allow_renewal ? (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[11px] font-medium border border-emerald-100">
                            <CheckCircle2 className="w-3 h-3 text-emerald-500" /> Auto-Renew
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 text-[11px] font-medium border border-purple-100">
                            <XCircle className="w-3 h-3 text-purple-500" /> No Renewal
                          </span>
                        )}
                        {p.auto_close_on_expiry && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-rose-50 text-rose-700 text-[11px] font-medium border border-rose-100">
                            Auto Close
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          p.is_active
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-slate-100 text-slate-500'
                        }`}
                      >
                        {p.is_active ? 'Active' : 'Archived'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => openEditModal(p)}
                          className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition"
                          title="Edit plan"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        {p.is_active && (
                          <button
                            onClick={() => handleArchivePlan(p)}
                            className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                            title="Archive plan"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Plan Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-bold text-slate-900 text-base">
                {editingPlan ? 'Edit Subscription Plan' : 'Create Subscription Plan'}
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSavePlan} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                  {formError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Plan Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Enterprise Monthly"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Billing Cadence *</label>
                  <select
                    value={form.cadence}
                    onChange={(e) => setForm({ ...form, cadence: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                    <option value="yearly">Yearly</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Base Price ($) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    placeholder="200.00"
                    value={form.base_price}
                    onChange={(e) => setForm({ ...form, base_price: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Minimum Quantity *</label>
                <input
                  type="number"
                  min="1"
                  required
                  value={form.min_quantity}
                  onChange={(e) => setForm({ ...form, min_quantity: parseInt(e.target.value) || 1 })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Available From</label>
                  <input
                    type="date"
                    value={form.available_from}
                    onChange={(e) => setForm({ ...form, available_from: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Available To</label>
                  <input
                    type="date"
                    value={form.available_to}
                    onChange={(e) => setForm({ ...form, available_to: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 space-y-2.5">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Lifecycle Policies
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <label className="flex items-center gap-2 cursor-pointer p-2 rounded-lg border border-slate-200 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={form.allow_pause}
                      onChange={(e) => setForm({ ...form, allow_pause: e.target.checked })}
                      className="rounded text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="font-medium text-slate-700">Allow Pause</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer p-2 rounded-lg border border-slate-200 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={form.allow_early_close}
                      onChange={(e) => setForm({ ...form, allow_early_close: e.target.checked })}
                      className="rounded text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="font-medium text-slate-700">Allow Early Close</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer p-2 rounded-lg border border-slate-200 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={form.allow_renewal}
                      onChange={(e) => setForm({ ...form, allow_renewal: e.target.checked })}
                      className="rounded text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="font-medium text-slate-700">Allow Auto-Renewal</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer p-2 rounded-lg border border-slate-200 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={form.auto_close_on_expiry}
                      onChange={(e) => setForm({ ...form, auto_close_on_expiry: e.target.checked })}
                      className="rounded text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="font-medium text-slate-700">Auto Close on Expiry</span>
                  </label>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {submitting ? 'Saving...' : editingPlan ? 'Update Plan' : 'Create Plan'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

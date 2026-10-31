import React, { useState, useEffect, useCallback } from 'react';
import {
  api,
  TaxRuleApiItem,
  DiscountRuleApiItem,
  ProductApiItem,
  PlanApiItem,
  CalculatePreviewResult,
  CreateTaxRulePayload,
  UpdateTaxRulePayload,
  CreateDiscountRulePayload,
  UpdateDiscountRulePayload,
  CalculatePreviewPayload,
} from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { AlertBanner } from '../components/common/AlertBanner';
import {
  Percent,
  Calculator,
  Plus,
  RefreshCw,
  Edit2,
  Trash2,
  X,
  Receipt,
  Calendar,
  Layers,
  AlertTriangle,
} from 'lucide-react';

interface DiscountsAdminProps {
  onNavigate?: (tabKey: string) => void;
}

export const DiscountsAdmin: React.FC<DiscountsAdminProps> = ({ onNavigate }) => {
  const [activeSubTab, setActiveSubTab] = useState<'taxes' | 'discounts' | 'simulator'>('simulator');
  const [loading, setLoading] = useState<boolean>(true);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Taxes State
  const [taxes, setTaxes] = useState<TaxRuleApiItem[]>([]);
  const [showTaxModal, setShowTaxModal] = useState<boolean>(false);
  const [editingTax, setEditingTax] = useState<TaxRuleApiItem | null>(null);
  const [taxForm, setTaxForm] = useState<{ name: string; rate_percentage: string }>({
    name: '',
    rate_percentage: '10.00',
  });
  const [taxSubmitting, setTaxSubmitting] = useState<boolean>(false);
  const [taxFormError, setTaxFormError] = useState<string | null>(null);

  // Discounts State
  const [discounts, setDiscounts] = useState<DiscountRuleApiItem[]>([]);
  const [showDiscountModal, setShowDiscountModal] = useState<boolean>(false);
  const [editingDiscount, setEditingDiscount] = useState<DiscountRuleApiItem | null>(null);
  const [discountForm, setDiscountForm] = useState<{
    name: string;
    discount_type: 'percentage' | 'fixed';
    value: string;
    scope: 'subscription' | 'product';
    target_product_id: string;
    min_spend: string;
    min_quantity: number;
    max_usage_limit: string;
    valid_from: string;
    valid_to: string;
  }>({
    name: '',
    discount_type: 'percentage',
    value: '10.00',
    scope: 'subscription',
    target_product_id: '',
    min_spend: '0.00',
    min_quantity: 0,
    max_usage_limit: '',
    valid_from: new Date().toISOString().split('T')[0],
    valid_to: new Date(Date.now() + 365 * 86400000).toISOString().split('T')[0],
  });
  const [discountSubmitting, setDiscountSubmitting] = useState<boolean>(false);
  const [discountFormError, setDiscountFormError] = useState<string | null>(null);

  // Catalog data for simulator
  const [catalogProducts, setCatalogProducts] = useState<ProductApiItem[]>([]);
  const [catalogPlans, setCatalogPlans] = useState<PlanApiItem[]>([]);

  // Simulator State
  const [simPlanId, setSimPlanId] = useState<string>('');
  const [simLines, setSimLines] = useState<
    { id: string; product_id: string; variant_id: string; quantity: number }[]
  >([]);
  const [simDiscountId, setSimDiscountId] = useState<string>('');
  const [simTaxId, setSimTaxId] = useState<string>('');
  const [simResult, setSimResult] = useState<CalculatePreviewResult | null>(null);
  const [simCalculating, setSimCalculating] = useState<boolean>(false);

  const fetchAllData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [taxList, discList, prodList, planList] = await Promise.all([
        api.getAllTaxRules(),
        api.getAllDiscountRules(),
        api.getAllProducts(),
        api.getPlans(),
      ]);
      setTaxes(taxList);
      setDiscounts(discList);
      setCatalogProducts(prodList);
      setCatalogPlans(planList);

      // Auto initialize simulator with first product if empty
      if (prodList.length > 0 && simLines.length === 0) {
        const firstProd = prodList[0];
        const firstVar = firstProd.variants && firstProd.variants.length > 0 ? firstProd.variants[0].id : '';
        setSimLines([{ id: 'line-1', product_id: firstProd.id, variant_id: firstVar || '', quantity: 1 }]);
      }
      if (planList.length > 0 && !simPlanId) {
        setSimPlanId(planList[0].id);
      }
      if (taxList.length > 0 && !simTaxId) {
        setSimTaxId(taxList[0].id);
      }
      if (discList.length > 0 && !simDiscountId) {
        setSimDiscountId(discList[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  // Tax Handlers
  const openCreateTax = () => {
    setEditingTax(null);
    setTaxForm({ name: '', rate_percentage: '10.00' });
    setTaxFormError(null);
    setShowTaxModal(true);
  };

  const openEditTax = (t: TaxRuleApiItem) => {
    setEditingTax(t);
    setTaxForm({ name: t.name, rate_percentage: String(t.rate_percentage) });
    setTaxFormError(null);
    setShowTaxModal(true);
  };

  const handleSaveTax = async (e: React.FormEvent) => {
    e.preventDefault();
    setTaxFormError(null);
    const rate = parseFloat(taxForm.rate_percentage);
    if (isNaN(rate) || rate < 0 || rate > 100) {
      setTaxFormError('Tax rate percentage must be between 0.00% and 100.00%.');
      return;
    }

    setTaxSubmitting(true);
    try {
      if (editingTax) {
        const payload: UpdateTaxRulePayload = {
          name: taxForm.name.trim(),
          rate_percentage: taxForm.rate_percentage,
        };
        await api.updateTaxRule(editingTax.id, payload);
        setFeedback({ type: 'success', message: `Tax Rule "${taxForm.name}" updated.` });
      } else {
        const payload: CreateTaxRulePayload = {
          name: taxForm.name.trim(),
          rate_percentage: taxForm.rate_percentage,
        };
        await api.createTaxRule(payload);
        setFeedback({ type: 'success', message: `Tax Rule "${taxForm.name}" created.` });
      }
      setShowTaxModal(false);
      fetchAllData();
    } catch (err) {
      setTaxFormError(err instanceof Error ? err.message : 'Failed to save tax rule.');
    } finally {
      setTaxSubmitting(false);
    }
  };

  const handleArchiveTax = async (t: TaxRuleApiItem) => {
    if (!window.confirm(`Archive tax rule "${t.name}"?`)) return;
    try {
      await api.archiveTaxRule(t.id);
      setFeedback({ type: 'success', message: `Tax Rule "${t.name}" archived.` });
      fetchAllData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to archive tax rule.' });
    }
  };

  // Discount Handlers
  const openCreateDiscount = () => {
    setEditingDiscount(null);
    setDiscountForm({
      name: '',
      discount_type: 'percentage',
      value: '10.00',
      scope: 'subscription',
      target_product_id: '',
      min_spend: '0.00',
      min_quantity: 0,
      max_usage_limit: '',
      valid_from: new Date().toISOString().split('T')[0],
      valid_to: new Date(Date.now() + 365 * 86400000).toISOString().split('T')[0],
    });
    setDiscountFormError(null);
    setShowDiscountModal(true);
  };

  const openEditDiscount = (d: DiscountRuleApiItem) => {
    setEditingDiscount(d);
    setDiscountForm({
      name: d.name,
      discount_type: d.discount_type,
      value: String(d.value),
      scope: d.scope,
      target_product_id: d.target_product_id || '',
      min_spend: String(d.min_spend),
      min_quantity: d.min_quantity,
      max_usage_limit: d.max_usage_limit !== null && d.max_usage_limit !== undefined ? String(d.max_usage_limit) : '',
      valid_from: d.valid_from,
      valid_to: d.valid_to,
    });
    setDiscountFormError(null);
    setShowDiscountModal(true);
  };

  const handleSaveDiscount = async (e: React.FormEvent) => {
    e.preventDefault();
    setDiscountFormError(null);

    const val = parseFloat(discountForm.value);
    if (isNaN(val) || val <= 0) {
      setDiscountFormError('Discount value must be greater than zero.');
      return;
    }
    if (discountForm.discount_type === 'percentage' && val > 100) {
      setDiscountFormError('Percentage discount value cannot exceed 100%.');
      return;
    }
    if (discountForm.valid_from > discountForm.valid_to) {
      setDiscountFormError('Valid from date cannot be after valid to date.');
      return;
    }
    if (discountForm.scope === 'product' && !discountForm.target_product_id) {
      setDiscountFormError('A target product is required when discount scope is set to "product".');
      return;
    }

    setDiscountSubmitting(true);
    try {
      if (editingDiscount) {
        const payload: UpdateDiscountRulePayload = {
          name: discountForm.name.trim(),
          discount_type: discountForm.discount_type,
          value: discountForm.value,
          scope: discountForm.scope,
          target_product_id: discountForm.target_product_id || undefined,
          min_spend: discountForm.min_spend,
          min_quantity: discountForm.min_quantity,
          max_usage_limit: discountForm.max_usage_limit ? parseInt(discountForm.max_usage_limit) : undefined,
          valid_from: discountForm.valid_from,
          valid_to: discountForm.valid_to,
        };
        await api.updateDiscountRule(editingDiscount.id, payload);
        setFeedback({ type: 'success', message: `Discount "${discountForm.name}" updated.` });
      } else {
        const payload: CreateDiscountRulePayload = {
          name: discountForm.name.trim(),
          discount_type: discountForm.discount_type,
          value: discountForm.value,
          scope: discountForm.scope,
          target_product_id: discountForm.target_product_id || undefined,
          min_spend: discountForm.min_spend,
          min_quantity: discountForm.min_quantity,
          max_usage_limit: discountForm.max_usage_limit ? parseInt(discountForm.max_usage_limit) : undefined,
          valid_from: discountForm.valid_from,
          valid_to: discountForm.valid_to,
        };
        await api.createDiscountRule(payload);
        setFeedback({ type: 'success', message: `Discount "${discountForm.name}" created.` });
      }
      setShowDiscountModal(false);
      fetchAllData();
    } catch (err) {
      setDiscountFormError(err instanceof Error ? err.message : 'Failed to save discount rule.');
    } finally {
      setDiscountSubmitting(false);
    }
  };

  const handleArchiveDiscount = async (d: DiscountRuleApiItem) => {
    if (!window.confirm(`Archive discount rule "${d.name}"?`)) return;
    try {
      await api.archiveDiscountRule(d.id);
      setFeedback({ type: 'success', message: `Discount Rule "${d.name}" archived.` });
      fetchAllData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to archive discount rule.' });
    }
  };

  // Simulator Handlers
  const handleAddSimLine = () => {
    if (catalogProducts.length === 0) return;
    const prod = catalogProducts[0];
    const vId = prod.variants && prod.variants.length > 0 ? prod.variants[0].id : '';
    setSimLines([...simLines, { id: `line-${Date.now()}`, product_id: prod.id, variant_id: vId, quantity: 1 }]);
  };

  const handleRemoveSimLine = (idx: number) => {
    setSimLines(simLines.filter((_, i) => i !== idx));
  };

  const handleSimLineChange = (idx: number, field: string, val: string | number) => {
    const updated = [...simLines];
    if (field === 'product_id') {
      const prod = catalogProducts.find((p) => p.id === val);
      const vId = prod && prod.variants && prod.variants.length > 0 ? prod.variants[0].id : '';
      updated[idx] = { ...updated[idx], product_id: String(val), variant_id: vId };
    } else {
      updated[idx] = { ...updated[idx], [field]: val };
    }
    setSimLines(updated);
  };

  const runSimulation = useCallback(async () => {
    setSimCalculating(true);
    try {
      const payload: CalculatePreviewPayload = {
        plan_id: simPlanId || undefined,
        product_lines: simLines.map((l) => ({
          product_id: l.product_id,
          variant_id: l.variant_id || undefined,
          quantity: l.quantity,
          tax_rule_id: simTaxId || undefined,
        })),
        discount_rule_id: simDiscountId || undefined,
        default_tax_rule_id: simTaxId || undefined,
      };

      const result = await api.calculatePreview(payload);
      setSimResult(result);
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to calculate quote preview.',
      });
    } finally {
      setSimCalculating(false);
    }
  }, [simPlanId, simLines, simDiscountId, simTaxId]);

  useEffect(() => {
    if (activeSubTab === 'simulator' && simLines.length > 0) {
      runSimulation();
    }
  }, [activeSubTab, simPlanId, simLines, simDiscountId, simTaxId, runSimulation]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Taxes, Discounts & Quote Simulator"
        subtitle="Manage tax codes, admin discount rules with usage limits, and test exact pricing calculations with brand variant adjustments."
        breadcrumbs={[
          { label: 'Brightloop', tabKey: 'dashboard' },
          { label: 'Catalog & Configuration', tabKey: 'catalog' },
          { label: 'Taxes & Discounts' },
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
              onClick={fetchAllData}
              className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            {activeSubTab === 'taxes' && (
              <button
                onClick={openCreateTax}
                className="px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-xs sm:text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-1.5 shadow-xs"
              >
                <Plus className="w-4 h-4" />
                <span>Add Tax Rule</span>
              </button>
            )}
            {activeSubTab === 'discounts' && (
              <button
                onClick={openCreateDiscount}
                className="px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-xs sm:text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-1.5 shadow-xs"
              >
                <Plus className="w-4 h-4" />
                <span>Create Discount</span>
              </button>
            )}
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

      {error && <ErrorState message={error} onRetry={fetchAllData} />}

      {/* Sub Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200">
        <button
          onClick={() => setActiveSubTab('simulator')}
          className={`flex items-center gap-2 py-3 px-4 text-sm font-semibold border-b-2 transition ${
            activeSubTab === 'simulator'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Calculator className="w-4 h-4" />
          <span>Interactive Quote Simulator</span>
        </button>
        <button
          onClick={() => setActiveSubTab('discounts')}
          className={`flex items-center gap-2 py-3 px-4 text-sm font-semibold border-b-2 transition ${
            activeSubTab === 'discounts'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Percent className="w-4 h-4" />
          <span>Discount Rules ({discounts.length})</span>
        </button>
        <button
          onClick={() => setActiveSubTab('taxes')}
          className={`flex items-center gap-2 py-3 px-4 text-sm font-semibold border-b-2 transition ${
            activeSubTab === 'taxes'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Receipt className="w-4 h-4" />
          <span>Tax Rules ({taxes.length})</span>
        </button>
      </div>

      {/* ---------------- SIMULATOR VIEW ---------------- */}
      {activeSubTab === 'simulator' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Controls Column */}
          <div className="lg:col-span-6 space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="font-bold text-slate-900 text-sm flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-600" />
                  <span>Configure Quote Scenario</span>
                </div>
                <span className="text-xs bg-indigo-50 text-indigo-700 px-2.5 py-0.5 rounded-full font-medium">
                  Live Preview
                </span>
              </div>

              {/* Plan Picker */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Subscription Plan (Base Fee)
                </label>
                <select
                  value={simPlanId}
                  onChange={(e) => setSimPlanId(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">No Plan Base Fee</option>
                  {catalogPlans.map((pl) => (
                    <option key={pl.id} value={pl.id}>
                      {pl.name} (${Number(pl.base_price).toFixed(2)} / {pl.cadence})
                    </option>
                  ))}
                </select>
              </div>

              {/* Product Lines */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-700">Product Line Items</label>
                  <button
                    type="button"
                    onClick={handleAddSimLine}
                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Item</span>
                  </button>
                </div>

                {simLines.map((line, idx) => {
                  const currentProd = catalogProducts.find((p) => p.id === line.product_id);
                  const variants = currentProd?.variants || [];

                  return (
                    <div
                      key={line.id}
                      className="p-3 bg-slate-50/80 rounded-xl border border-slate-200 space-y-2 relative text-xs"
                    >
                      <div className="grid grid-cols-12 gap-2">
                        <div className="col-span-6">
                          <label className="block text-[11px] font-medium text-slate-600 mb-1">Product</label>
                          <select
                            value={line.product_id}
                            onChange={(e) => handleSimLineChange(idx, 'product_id', e.target.value)}
                            className="w-full px-2 py-1.5 border border-slate-300 rounded-lg bg-white text-xs"
                          >
                            {catalogProducts.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.name} (${Number(p.sales_price).toFixed(2)})
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="col-span-4">
                          <label className="block text-[11px] font-medium text-slate-600 mb-1">
                            Variant (Adjustment)
                          </label>
                          <select
                            value={line.variant_id}
                            onChange={(e) => handleSimLineChange(idx, 'variant_id', e.target.value)}
                            className="w-full px-2 py-1.5 border border-slate-300 rounded-lg bg-white text-xs"
                          >
                            <option value="">Standard ($0.00)</option>
                            {variants.map((v) => (
                              <option key={v.id} value={v.id}>
                                {v.name} (+${Number(v.price_adjustment).toFixed(2)})
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="col-span-2">
                          <label className="block text-[11px] font-medium text-slate-600 mb-1">Qty</label>
                          <input
                            type="number"
                            min="1"
                            value={line.quantity}
                            onChange={(e) =>
                              handleSimLineChange(idx, 'quantity', parseInt(e.target.value) || 1)
                            }
                            className="w-full px-2 py-1.5 border border-slate-300 rounded-lg bg-white text-xs font-mono"
                          />
                        </div>
                      </div>

                      {simLines.length > 1 && (
                        <div className="flex justify-end pt-1">
                          <button
                            type="button"
                            onClick={() => handleRemoveSimLine(idx)}
                            className="text-red-500 hover:text-red-700 text-[11px] flex items-center gap-0.5"
                          >
                            <Trash2 className="w-3 h-3" /> Remove
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Discounts & Taxes Selection */}
              <div className="grid grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Discount Rule</label>
                  <select
                    value={simDiscountId}
                    onChange={(e) => setSimDiscountId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="">No Discount</option>
                    {discounts.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} ({d.discount_type === 'percentage' ? `${d.value}%` : `$${d.value}`})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Tax Rule</label>
                  <select
                    value={simTaxId}
                    onChange={(e) => setSimTaxId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="">No Tax</option>
                    {taxes.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.rate_percentage}%)
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <button
                type="button"
                onClick={runSimulation}
                disabled={simCalculating}
                className="w-full py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition flex items-center justify-center gap-2 shadow-xs"
              >
                <Calculator className="w-4 h-4" />
                <span>{simCalculating ? 'Calculating Quote...' : 'Recalculate Quote'}</span>
              </button>
            </div>
          </div>

          {/* Results Column */}
          <div className="lg:col-span-6 space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="font-bold text-slate-900 text-sm">Exact Calculation Breakdown</div>
                <div className="text-xs text-slate-500">Half-Up Cent Rounding</div>
              </div>

              {simResult ? (
                <div className="space-y-4">
                  {simResult.warnings && simResult.warnings.length > 0 && (
                    <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-lg space-y-1">
                      <div className="font-semibold flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4 text-amber-600" /> Rule Threshold Warnings
                      </div>
                      <ul className="list-disc pl-5 space-y-0.5">
                        {simResult.warnings.map((w, idx) => (
                          <li key={idx}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Line Items Table */}
                  <div className="border border-slate-200 rounded-xl overflow-hidden text-xs">
                    <table className="w-full text-left">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                        <tr>
                          <th className="p-2.5">Item & Variant</th>
                          <th className="p-2.5 text-right">Unit Price</th>
                          <th className="p-2.5 text-center">Qty</th>
                          <th className="p-2.5 text-right">Subtotal</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {simResult.lines.map((ln, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/50">
                            <td className="p-2.5">
                              <div className="font-semibold text-slate-900">{ln.description}</div>
                              {Number(ln.price_adjustment) !== 0 && (
                                <div className="text-[11px] text-indigo-600 font-medium mt-0.5">
                                  Includes Variant Adj: +${Number(ln.price_adjustment).toFixed(2)}
                                </div>
                              )}
                            </td>
                            <td className="p-2.5 text-right font-mono text-slate-700">
                              ${Number(ln.unit_price).toFixed(2)}
                            </td>
                            <td className="p-2.5 text-center font-mono text-slate-700">{ln.quantity}</td>
                            <td className="p-2.5 text-right font-mono font-bold text-slate-900">
                              ${Number(ln.subtotal).toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Summary Totals */}
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2 text-xs">
                    <div className="flex justify-between text-slate-600">
                      <span>Gross Subtotal:</span>
                      <span className="font-mono font-semibold text-slate-900">
                        ${Number(simResult.subtotal).toFixed(2)}
                      </span>
                    </div>

                    <div className="flex justify-between text-emerald-700">
                      <span>Discount ({simResult.discount_name || 'None'}):</span>
                      <span className="font-mono font-semibold">
                        -${Number(simResult.discount_amount).toFixed(2)}
                      </span>
                    </div>

                    <div className="flex justify-between text-slate-600">
                      <span>Estimated Tax:</span>
                      <span className="font-mono font-semibold text-slate-900">
                        +${Number(simResult.tax_amount).toFixed(2)}
                      </span>
                    </div>

                    <div className="pt-2 border-t border-slate-200 flex justify-between items-baseline text-sm">
                      <span className="font-bold text-slate-900">Final Total:</span>
                      <span className="font-mono font-extrabold text-indigo-700 text-lg">
                        ${Number(simResult.total_amount).toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-slate-400 text-xs">
                  Click &quot;Recalculate Quote&quot; to test your scenario.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ---------------- DISCOUNT RULES VIEW ---------------- */}
      {activeSubTab === 'discounts' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          {loading ? (
            <LoadingState message="Loading discount rules..." rows={3} />
          ) : discounts.length === 0 ? (
            <EmptyState
              title="No discount rules configured"
              description="Create your first fixed or percentage discount rule."
              action={{ label: 'Create Discount', onClick: openCreateDiscount }}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm min-w-[800px]">
                <thead>
                  <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                    <th className="py-3 px-4">Rule Name</th>
                    <th className="py-3 px-4">Type & Value</th>
                    <th className="py-3 px-4">Scope</th>
                    <th className="py-3 px-4">Criteria</th>
                    <th className="py-3 px-4 text-center">Usage Limit</th>
                    <th className="py-3 px-4">Validity Window</th>
                    <th className="py-3 px-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {discounts.map((d) => (
                    <tr key={d.id} className="hover:bg-slate-50/60 transition">
                      <td className="py-3.5 px-4 font-semibold text-slate-900">{d.name}</td>
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-50 text-purple-700 border border-purple-100">
                          {d.discount_type === 'percentage' ? `${d.value}% Off` : `$${d.value} Flat`}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 capitalize text-xs">
                        <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-medium">
                          {d.scope}
                        </span>
                        {d.target_product_name && (
                          <div className="text-[11px] text-slate-500 mt-0.5">
                            Target: {d.target_product_name}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600 space-y-0.5">
                        {Number(d.min_spend) > 0 && <div>Min Spend: ${Number(d.min_spend).toFixed(2)}</div>}
                        {d.min_quantity > 0 && <div>Min Qty: {d.min_quantity}</div>}
                        {Number(d.min_spend) === 0 && d.min_quantity === 0 && (
                          <span className="text-slate-400 italic">None</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-center text-xs">
                        <span className="font-mono font-semibold text-slate-900">{d.current_usage_count}</span>
                        <span className="text-slate-400"> / {d.max_usage_limit ?? '∞'}</span>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span>{d.valid_from}</span>
                          <span className="text-slate-400">→</span>
                          <span>{d.valid_to}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            onClick={() => openEditDiscount(d)}
                            className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition"
                            title="Edit discount"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          {d.is_active && (
                            <button
                              onClick={() => handleArchiveDiscount(d)}
                              className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                              title="Archive discount"
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
      )}

      {/* ---------------- TAX RULES VIEW ---------------- */}
      {activeSubTab === 'taxes' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          {loading ? (
            <LoadingState message="Loading tax rules..." rows={3} />
          ) : taxes.length === 0 ? (
            <EmptyState
              title="No tax rules configured"
              description="Configure your state, VAT, or GST tax rates."
              action={{ label: 'Add Tax Rule', onClick: openCreateTax }}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm min-w-[600px]">
                <thead>
                  <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                    <th className="py-3 px-4">Tax Name</th>
                    <th className="py-3 px-4 text-right">Rate (%)</th>
                    <th className="py-3 px-4 text-center">Status</th>
                    <th className="py-3 px-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {taxes.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50/60 transition">
                      <td className="py-3.5 px-4 font-semibold text-slate-900">{t.name}</td>
                      <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900">
                        {Number(t.rate_percentage).toFixed(2)}%
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            t.is_active
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          {t.is_active ? 'Active' : 'Archived'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            onClick={() => openEditTax(t)}
                            className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition"
                            title="Edit tax rule"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          {t.is_active && (
                            <button
                              onClick={() => handleArchiveTax(t)}
                              className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                              title="Archive tax rule"
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
      )}

      {/* Tax Modal */}
      {showTaxModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-bold text-slate-900 text-base">
                {editingTax ? 'Edit Tax Rule' : 'Add Tax Rule'}
              </h3>
              <button onClick={() => setShowTaxModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSaveTax} className="p-6 space-y-4">
              {taxFormError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                  {taxFormError}
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Tax Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Standard VAT or GST 18%"
                  value={taxForm.name}
                  onChange={(e) => setTaxForm({ ...taxForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Tax Rate Percentage (0 - 100%) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  required
                  value={taxForm.rate_percentage}
                  onChange={(e) => setTaxForm({ ...taxForm, rate_percentage: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowTaxModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={taxSubmitting}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {taxSubmitting ? 'Saving...' : editingTax ? 'Update Tax' : 'Create Tax'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Discount Modal */}
      {showDiscountModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-bold text-slate-900 text-base">
                {editingDiscount ? 'Edit Discount Rule' : 'Create Discount Rule'}
              </h3>
              <button onClick={() => setShowDiscountModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSaveDiscount} className="p-6 space-y-4">
              {discountFormError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                  {discountFormError}
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Discount Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Launch Special 10%"
                  value={discountForm.name}
                  onChange={(e) => setDiscountForm({ ...discountForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Type *</label>
                  <select
                    value={discountForm.discount_type}
                    onChange={(e) =>
                      setDiscountForm({
                        ...discountForm,
                        discount_type: e.target.value as 'percentage' | 'fixed',
                      })
                    }
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="percentage">Percentage (%)</option>
                    <option value="fixed">Fixed Amount ($)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Value *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={discountForm.value}
                    onChange={(e) => setDiscountForm({ ...discountForm, value: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Scope *</label>
                  <select
                    value={discountForm.scope}
                    onChange={(e) =>
                      setDiscountForm({
                        ...discountForm,
                        scope: e.target.value as 'subscription' | 'product',
                      })
                    }
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="subscription">Subscription (Global)</option>
                    <option value="product">Specific Product</option>
                  </select>
                </div>
                {discountForm.scope === 'product' && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Target Product *</label>
                    <select
                      value={discountForm.target_product_id}
                      onChange={(e) =>
                        setDiscountForm({ ...discountForm, target_product_id: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="">Select Product</option>
                      {catalogProducts.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Min Spend ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={discountForm.min_spend}
                    onChange={(e) => setDiscountForm({ ...discountForm, min_spend: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Usage Cap (Redemption Limit)
                  </label>
                  <input
                    type="number"
                    min="1"
                    placeholder="Unlimited"
                    value={discountForm.max_usage_limit}
                    onChange={(e) =>
                      setDiscountForm({ ...discountForm, max_usage_limit: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Valid From *</label>
                  <input
                    type="date"
                    required
                    value={discountForm.valid_from}
                    onChange={(e) => setDiscountForm({ ...discountForm, valid_from: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Valid To *</label>
                  <input
                    type="date"
                    required
                    value={discountForm.valid_to}
                    onChange={(e) => setDiscountForm({ ...discountForm, valid_to: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowDiscountModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={discountSubmitting}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {discountSubmitting ? 'Saving...' : editingDiscount ? 'Update Discount' : 'Create Discount'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

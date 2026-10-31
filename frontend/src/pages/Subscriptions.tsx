import React, { useEffect, useState, useCallback } from 'react';
import {
  api,
  SubscriptionApiItem,
  SubscriptionDetailApiItem,
  QuotationTemplateApiItem,
  CustomerAccountApiItem,
  ProductApiItem,
  PlanApiItem,
  CreateSubscriptionPayload,
  CreateQuotationTemplatePayload,
} from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { SearchAndFilterBar, FilterOption, SortOption } from '../components/common/SearchAndFilterBar';
import { PaginationControls } from '../components/common/PaginationControls';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { AlertBanner } from '../components/common/AlertBanner';
import {
  Plus,
  CheckCircle,
  Clock,
  Pause,
  RefreshCw,
  XCircle,
  FileText,
  Calendar,
  Send,
  Play,
  RotateCw,
  Layers,
  History,
  X,
  ChevronRight,
  Trash2,
} from 'lucide-react';

const formatDateInput = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

const STATUS_OPTIONS: FilterOption[] = [
  { label: 'Active', value: 'active' },
  { label: 'Quotation', value: 'quotation' },
  { label: 'Confirmed', value: 'confirmed' },
  { label: 'Paused', value: 'paused' },
  { label: 'Closed', value: 'closed' },
  { label: 'Draft', value: 'draft' },
];

const SORT_OPTIONS: SortOption[] = [
  { label: 'Newest First', sortBy: 'created_at', sortOrder: 'desc' },
  { label: 'Oldest First', sortBy: 'created_at', sortOrder: 'asc' },
  { label: 'Subscription # (A-Z)', sortBy: 'subscription_number', sortOrder: 'asc' },
  { label: 'Next Billing Date', sortBy: 'next_billing_date', sortOrder: 'asc' },
];

interface SubscriptionsProps {
  onNavigate?: (tabKey: string) => void;
}

export const Subscriptions: React.FC<SubscriptionsProps> = ({ onNavigate }) => {
  const [activeTab, setActiveTab] = useState<'subscriptions' | 'templates'>('subscriptions');

  // Subscriptions List State
  const [subscriptions, setSubscriptions] = useState<SubscriptionApiItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Pagination & Filters State
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortValue, setSortValue] = useState<string>('created_at-desc');

  // Supporting Domain Data
  const [customerAccounts, setCustomerAccounts] = useState<CustomerAccountApiItem[]>([]);
  const [plans, setPlans] = useState<PlanApiItem[]>([]);
  const [products, setProducts] = useState<ProductApiItem[]>([]);
  const [templates, setTemplates] = useState<QuotationTemplateApiItem[]>([]);

  // Subscription Detail Drawer State
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null);
  const [selectedSubDetail, setSelectedSubDetail] = useState<SubscriptionDetailApiItem | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [transitioning, setTransitioning] = useState<boolean>(false);

  // Create Quote / Subscription Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [createForm, setCreateForm] = useState<{
    customer_account_id: string;
    plan_id: string;
    template_id: string;
    start_date: string;
    expiry_date: string;
    quote_valid_until: string;
    status: 'draft' | 'quotation';
    lines: { product_id: string; variant_id: string; quantity: number }[];
  }>({
    customer_account_id: '',
    plan_id: '',
    template_id: '',
    start_date: formatDateInput(new Date()),
    expiry_date: '',
    quote_valid_until: '',
    status: 'quotation',
    lines: [],
  });
  const [createSubmitting, setCreateSubmitting] = useState<boolean>(false);
  const [createFormError, setCreateFormError] = useState<string | null>(null);

  // Template Modal State
  const [showTemplateModal, setShowTemplateModal] = useState<boolean>(false);
  const [templateForm, setTemplateForm] = useState<{
    name: string;
    validity_days: number;
    default_plan_id: string;
    default_lines: { product_id: string; variant_id: string; quantity: number }[];
  }>({
    name: '',
    validity_days: 30,
    default_plan_id: '',
    default_lines: [],
  });
  const [templateSubmitting, setTemplateSubmitting] = useState<boolean>(false);
  const [templateFormError, setTemplateFormError] = useState<string | null>(null);

  const fetchSubscriptions = useCallback(async () => {
    setLoading(true);
    setError(null);

    const [sortBy, sortOrder] = sortValue.split('-') as [string, 'asc' | 'desc'];

    try {
      const data = await api.getSubscriptions({
        page,
        pageSize,
        search: searchQuery || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        sortBy,
        sortOrder,
      });

      setSubscriptions(data.items);
      setTotal(data.total);
      setTotalPages(data.totalPages);
      setIsLive(true);
    } catch (reason) {
      setSubscriptions([]);
      setIsLive(false);
      setError(reason instanceof Error ? reason.message : 'Could not load subscriptions.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, searchQuery, statusFilter, sortValue]);

  const fetchSupportingData = useCallback(async () => {
    try {
      const [custs, pls, prods, tpls] = await Promise.all([
        api.getCustomerAccounts().catch(() => []),
        api.getPlans().catch(() => []),
        api.getAllProducts().catch(() => []),
        api.getAllQuotationTemplates().catch(() => []),
      ]);
      setCustomerAccounts(custs);
      setPlans(pls);
      setProducts(prods);
      setTemplates(tpls);
    } catch {
      // Ignore background errors
    }
  }, []);

  useEffect(() => {
    fetchSubscriptions();
    fetchSupportingData();
  }, [fetchSubscriptions, fetchSupportingData]);

  // Load Full Subscription Details
  const handleOpenDetail = async (id: string) => {
    setSelectedSubId(id);
    setDetailLoading(true);
    try {
      const detail = await api.getSubscription(id);
      setSelectedSubDetail(detail);
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to load subscription details.',
      });
      setSelectedSubId(null);
    } finally {
      setDetailLoading(false);
    }
  };

  // State Transition Action Handlers
  const handleTransition = async (action: string, reason?: string, duration?: number) => {
    if (!selectedSubId) return;
    setTransitioning(true);
    try {
      await api.transitionSubscriptionStatus(selectedSubId, action, reason, duration);
      setFeedback({ type: 'success', message: `Status updated successfully (${action}).` });
      // Refresh detail and list
      const updated = await api.getSubscription(selectedSubId);
      setSelectedSubDetail(updated);
      fetchSubscriptions();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : `Failed to perform action "${action}".`,
      });
    } finally {
      setTransitioning(false);
    }
  };

  // Template pre-fill handler for Create Quote
  const handleSelectTemplateInForm = (templateId: string) => {
    const tpl = templates.find((t) => t.id === templateId);
    if (!tpl) {
      setCreateForm((prev) => ({ ...prev, template_id: '' }));
      return;
    }

    const quoteStartDate = new Date();
    quoteStartDate.setDate(quoteStartDate.getDate() + tpl.validity_days);
    const quoteValidUntil = formatDateInput(quoteStartDate);

    const mappedLines = (tpl.default_lines || []).map((dl) => ({
      product_id: dl.product_id,
      variant_id: dl.product_variant_id || '',
      quantity: dl.quantity || 1,
    }));

    setCreateForm((prev) => ({
      ...prev,
      template_id: templateId,
      plan_id: tpl.default_plan_id || prev.plan_id,
      quote_valid_until: quoteValidUntil,
      lines: mappedLines.length > 0 ? mappedLines : prev.lines,
    }));
  };

  const handleOpenCreateModal = (presetTemplateId?: string) => {
    setCreateFormError(null);
    const initialCust = customerAccounts.length > 0 ? customerAccounts[0].id : '';
    const initialPlan = plans.length > 0 ? plans[0].id : '';
    const initialProd = products.length > 0 ? products[0].id : '';
    const initialVar = products[0]?.variants?.[0]?.id || '';

    setCreateForm({
      customer_account_id: initialCust,
      plan_id: initialPlan,
      template_id: '',
      start_date: formatDateInput(new Date()),
      expiry_date: '',
      quote_valid_until: '',
      status: 'quotation',
      lines: initialProd ? [{ product_id: initialProd, variant_id: initialVar, quantity: 1 }] : [],
    });

    if (presetTemplateId) {
      setTimeout(() => handleSelectTemplateInForm(presetTemplateId), 0);
    }
    setShowCreateModal(true);
  };

  const handleCreateSubscription = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateFormError(null);

    if (!createForm.customer_account_id) {
      setCreateFormError('Please select a customer account.');
      return;
    }
    if (!createForm.plan_id) {
      setCreateFormError('Please select a subscription plan.');
      return;
    }
    if (createForm.lines.length === 0) {
      setCreateFormError('Please add at least one product line.');
      return;
    }

    setCreateSubmitting(true);
    try {
      const payload: CreateSubscriptionPayload = {
        customer_account_id: createForm.customer_account_id,
        plan_id: createForm.plan_id,
        template_id: createForm.template_id || undefined,
        start_date: createForm.start_date || undefined,
        expiry_date: createForm.expiry_date || undefined,
        quote_valid_until: createForm.quote_valid_until || undefined,
        status: createForm.status,
        lines: createForm.lines.map((l) => ({
          product_id: l.product_id,
          product_variant_id: l.variant_id || undefined,
          quantity: l.quantity,
        })),
      };

      const created = await api.createSubscription(payload);
      setFeedback({
        type: 'success',
        message: `${created.status === 'quotation' ? 'Quotation' : 'Subscription'} ${created.subscription_number} created successfully.`,
      });
      setShowCreateModal(false);
      fetchSubscriptions();
      handleOpenDetail(created.id);
    } catch (err) {
      setCreateFormError(err instanceof Error ? err.message : 'Failed to create subscription.');
    } finally {
      setCreateSubmitting(false);
    }
  };

  // Quotation Template Creation
  const handleCreateTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    setTemplateFormError(null);

    if (!templateForm.name.trim()) {
      setTemplateFormError('Please enter a template name.');
      return;
    }

    setTemplateSubmitting(true);
    try {
      const payload: CreateQuotationTemplatePayload = {
        name: templateForm.name.trim(),
        validity_days: templateForm.validity_days,
        default_plan_id: templateForm.default_plan_id || undefined,
        default_lines: templateForm.default_lines.map((l) => ({
          product_id: l.product_id,
          product_variant_id: l.variant_id || undefined,
          quantity: l.quantity,
        })),
      };

      await api.createQuotationTemplate(payload);
      setFeedback({ type: 'success', message: `Template "${templateForm.name}" created successfully.` });
      setShowTemplateModal(false);
      fetchSupportingData();
    } catch (err) {
      setTemplateFormError(err instanceof Error ? err.message : 'Failed to create template.');
    } finally {
      setTemplateSubmitting(false);
    }
  };

  const handleDeleteTemplate = async (t: QuotationTemplateApiItem) => {
    if (!window.confirm(`Delete quotation template "${t.name}"?`)) return;
    try {
      await api.deleteQuotationTemplate(t.id);
      setFeedback({ type: 'success', message: `Template "${t.name}" deleted.` });
      fetchSupportingData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to delete template.' });
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
            <CheckCircle className="w-3 h-3" />
            Active
          </span>
        );
      case 'confirmed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800">
            <CheckCircle className="w-3 h-3" />
            Confirmed
          </span>
        );
      case 'quotation':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
            <Clock className="w-3 h-3" />
            Quotation
          </span>
        );
      case 'draft':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            <FileText className="w-3 h-3" />
            Draft
          </span>
        );
      case 'paused':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
            <Pause className="w-3 h-3" />
            Paused
          </span>
        );
      case 'closed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-700">
            <XCircle className="w-3 h-3" />
            Closed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Subscriptions & Quotation Templates"
        subtitle="Manage end-to-end subscription lifecycles, quotation templates, customer orders, and traceable status history."
        breadcrumbs={[
          { label: 'Brightloop', tabKey: 'dashboard' },
          { label: 'Operations', tabKey: 'dashboard' },
          { label: 'Subscriptions & Quotes' },
        ]}
        onSelectTab={onNavigate}
        badge={
          <span
            className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
              isLive ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
            }`}
          >
            {isLive ? '● Live API Data' : 'Connecting...'}
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                fetchSubscriptions();
                fetchSupportingData();
              }}
              className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
              title="Refresh"
              aria-label="Refresh subscriptions"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => handleOpenCreateModal()}
              className="px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-xs sm:text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-1.5 shadow-xs"
            >
              <Plus className="w-4 h-4" />
              <span>Create Quote / Order</span>
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

      {error && <ErrorState message={error} onRetry={fetchSubscriptions} />}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200">
        <button
          onClick={() => setActiveTab('subscriptions')}
          className={`flex items-center gap-2 py-3 px-4 text-sm font-semibold border-b-2 transition ${
            activeTab === 'subscriptions'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>Subscriptions & Quotations ({total})</span>
        </button>
        <button
          onClick={() => setActiveTab('templates')}
          className={`flex items-center gap-2 py-3 px-4 text-sm font-semibold border-b-2 transition ${
            activeTab === 'templates'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Quotation Templates ({templates.length})</span>
        </button>
      </div>

      {/* ---------------- SUBSCRIPTIONS LIST VIEW ---------------- */}
      {activeTab === 'subscriptions' && (
        <div className="space-y-4">
          <SearchAndFilterBar
            searchQuery={searchQuery}
            onSearchChange={(q) => {
              setSearchQuery(q);
              setPage(1);
            }}
            searchPlaceholder="Search subscription # or customer name..."
            statusFilter={statusFilter}
            onStatusChange={(s) => {
              setStatusFilter(s);
              setPage(1);
            }}
            statusOptions={STATUS_OPTIONS}
            sortValue={sortValue}
            onSortChange={(val) => {
              setSortValue(val);
              setPage(1);
            }}
            sortOptions={SORT_OPTIONS}
            onReset={() => {
              setSearchQuery('');
              setStatusFilter('all');
              setSortValue('created_at-desc');
              setPage(1);
            }}
          />

          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            {loading ? (
              <LoadingState message="Loading subscriptions from server..." rows={5} />
            ) : subscriptions.length === 0 ? (
              <EmptyState
                title="No subscriptions or quotes found"
                description="Create a new quote from a template or start from draft."
                action={{ label: 'Create Quote / Order', onClick: () => handleOpenCreateModal() }}
              />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-sm min-w-[750px]">
                    <thead>
                      <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                        <th className="py-3 px-4">Subscription #</th>
                        <th className="py-3 px-4">Customer</th>
                        <th className="py-3 px-4">Plan</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Next Billing Date</th>
                        <th className="py-3 px-4 text-right">Total Amount</th>
                        <th className="py-3 px-4 text-center">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {subscriptions.map((sub) => (
                        <tr
                          key={sub.id}
                          onClick={() => handleOpenDetail(sub.id)}
                          className="hover:bg-slate-50/70 transition cursor-pointer"
                        >
                          <td className="py-3.5 px-4 font-mono font-semibold text-indigo-600">
                            {sub.subscription_number}
                          </td>
                          <td className="py-3.5 px-4 font-semibold text-slate-900">{sub.customer_name}</td>
                          <td className="py-3.5 px-4 text-slate-700">{sub.plan_name}</td>
                          <td className="py-3.5 px-4">{getStatusBadge(sub.status)}</td>
                          <td className="py-3.5 px-4 font-mono text-slate-600 text-xs">
                            {sub.next_billing_date || (
                              <span className="text-slate-400 italic">Not scheduled</span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900">
                            ${Number(sub.total_amount).toFixed(2)}
                          </td>
                          <td className="py-3.5 px-4 text-center">
                            <span className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center justify-center gap-1">
                              View <ChevronRight className="w-3.5 h-3.5" />
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <PaginationControls
                  page={page}
                  pageSize={pageSize}
                  total={total}
                  totalPages={totalPages}
                  onPageChange={setPage}
                  onPageSizeChange={(sz) => {
                    setPageSize(sz);
                    setPage(1);
                  }}
                />
              </>
            )}
          </div>
        </div>
      )}

      {/* ---------------- QUOTATION TEMPLATES VIEW ---------------- */}
      {activeTab === 'templates' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
            <div>
              <div className="font-bold text-sm text-slate-900">Sales Quotation Templates</div>
              <div className="text-xs text-slate-500">
                Pre-bundle plans and default product lines for fast 1-click quotation generation.
              </div>
            </div>
            <button
              onClick={() => {
                setTemplateFormError(null);
                setTemplateForm({
                  name: '',
                  validity_days: 30,
                  default_plan_id: plans[0]?.id || '',
                  default_lines: products[0]
                    ? [{ product_id: products[0].id, variant_id: '', quantity: 1 }]
                    : [],
                });
                setShowTemplateModal(true);
              }}
              className="px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700 transition flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>New Template</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {templates.map((tpl) => (
              <div
                key={tpl.id}
                className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between space-y-4 hover:border-indigo-200 transition"
              >
                <div className="space-y-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-bold text-slate-900 text-base">{tpl.name}</h4>
                      <span className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        Validity: {tpl.validity_days} Days
                      </span>
                    </div>
                    <button
                      onClick={() => handleDeleteTemplate(tpl)}
                      className="p-1 text-slate-400 hover:text-red-600 rounded transition"
                      title="Delete template"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="pt-2 border-t border-slate-100 text-xs space-y-1">
                    <div className="text-slate-600">
                      <span className="font-semibold text-slate-700">Default Plan:</span>{' '}
                      {tpl.default_plan_name || 'None'}
                    </div>
                    <div className="text-slate-600">
                      <span className="font-semibold text-slate-700">Pre-configured Lines:</span>{' '}
                      {tpl.default_lines?.length || 0} item(s)
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleOpenCreateModal(tpl.id)}
                  className="w-full py-2 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Create Quote with this Template</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---------------- SUBSCRIPTION DETAIL & LIFECYCLE DRAWER ---------------- */}
      {selectedSubId && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white w-full max-w-2xl h-full shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right duration-200">
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <div className="flex items-center gap-3">
                  <h3 className="font-bold text-slate-900 text-lg font-mono">
                    {selectedSubDetail?.subscription_number}
                  </h3>
                  {selectedSubDetail && getStatusBadge(selectedSubDetail.status)}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {selectedSubDetail?.customer_name} • Plan: {selectedSubDetail?.plan_name}
                </div>
              </div>
              <button
                onClick={() => setSelectedSubId(null)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content Body */}
            {detailLoading || !selectedSubDetail ? (
              <div className="p-8">
                <LoadingState message="Loading agreement details and history..." rows={6} />
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Lifecycle Actions Banner */}
                <div className="bg-indigo-50/70 border border-indigo-100 p-4 rounded-xl space-y-3">
                  <div className="text-xs font-bold uppercase tracking-wider text-indigo-900">
                    Lifecycle & State Transition Actions
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {/* Draft Transitions */}
                    {selectedSubDetail.status === 'draft' && (
                      <button
                        onClick={() => handleTransition('issue_quote', 'Formal quote issued to client')}
                        disabled={transitioning}
                        className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700 transition flex items-center gap-1.5 shadow-xs"
                      >
                        <Send className="w-3.5 h-3.5" /> Issue Quotation
                      </button>
                    )}

                    {/* Quotation Transitions */}
                    {selectedSubDetail.status === 'quotation' && (
                      <>
                        <button
                          onClick={() => handleTransition('confirm', 'Customer accepted quote')}
                          disabled={transitioning}
                          className="px-3.5 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700 transition flex items-center gap-1.5 shadow-xs"
                        >
                          <CheckCircle className="w-3.5 h-3.5" /> Accept & Confirm
                        </button>
                        <button
                          onClick={() => handleTransition('close', 'Customer declined quotation')}
                          disabled={transitioning}
                          className="px-3 py-1.5 bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold hover:bg-slate-300 transition"
                        >
                          Decline Quote
                        </button>
                      </>
                    )}

                    {/* Confirmed Transitions */}
                    {selectedSubDetail.status === 'confirmed' && (
                      <button
                        onClick={() => handleTransition('activate')}
                        disabled={transitioning}
                        className="px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700 transition flex items-center gap-1.5 shadow-xs"
                      >
                        <Play className="w-3.5 h-3.5" /> Activate Subscription
                      </button>
                    )}

                    {/* Active Transitions */}
                    {selectedSubDetail.status === 'active' && (
                      <>
                        <button
                          onClick={() => handleTransition('pause', 'Staff paused subscription')}
                          disabled={transitioning}
                          className="px-3 py-1.5 bg-amber-600 text-white rounded-lg text-xs font-semibold hover:bg-amber-700 transition flex items-center gap-1.5 shadow-xs"
                        >
                          <Pause className="w-3.5 h-3.5" /> Pause
                        </button>
                        <button
                          onClick={() => handleTransition('renew')}
                          disabled={transitioning}
                          className="px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-semibold hover:bg-purple-700 transition flex items-center gap-1.5 shadow-xs"
                        >
                          <RotateCw className="w-3.5 h-3.5" /> Renew Agreement
                        </button>
                        <button
                          onClick={() => handleTransition('close', 'Early close requested')}
                          disabled={transitioning}
                          className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs font-semibold hover:bg-red-700 transition"
                        >
                          Close Subscription
                        </button>
                      </>
                    )}

                    {/* Paused Transitions */}
                    {selectedSubDetail.status === 'paused' && (
                      <>
                        <button
                          onClick={() => handleTransition('resume')}
                          disabled={transitioning}
                          className="px-3.5 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700 transition flex items-center gap-1.5 shadow-xs"
                        >
                          <Play className="w-3.5 h-3.5" /> Resume Subscription
                        </button>
                        <button
                          onClick={() => handleTransition('close', 'Closed while paused')}
                          disabled={transitioning}
                          className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs font-semibold hover:bg-red-700 transition"
                        >
                          Close
                        </button>
                      </>
                    )}

                    {selectedSubDetail.status === 'closed' && (
                      <span className="text-xs text-slate-500 italic">
                        This subscription is in the terminal closed state.
                      </span>
                    )}
                  </div>
                </div>

                {/* Agreement Metadata Card */}
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
                    <div className="font-bold uppercase tracking-wider text-slate-500 text-[10px]">
                      Customer & Billing
                    </div>
                    <div className="font-semibold text-slate-900 text-sm">{selectedSubDetail.customer_name}</div>
                    <div className="text-slate-600">{selectedSubDetail.customer_billing_email}</div>
                    <div className="text-slate-500">{selectedSubDetail.customer_address}</div>
                  </div>

                  <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
                    <div className="font-bold uppercase tracking-wider text-slate-500 text-[10px]">
                      Plan & Lifecycle Dates
                    </div>
                    <div className="font-semibold text-slate-900 text-sm capitalize">
                      {selectedSubDetail.plan_name} ({selectedSubDetail.plan_cadence})
                    </div>
                    <div className="text-slate-600">
                      Start: <span className="font-mono">{selectedSubDetail.start_date}</span>
                    </div>
                    <div className="text-slate-600">
                      Expiry:{' '}
                      <span className="font-mono">{selectedSubDetail.expiry_date || 'Open/Ongoing'}</span>
                    </div>
                    <div className="text-slate-600">
                      Quote valid until:{' '}
                      <span className="font-mono">{selectedSubDetail.quote_valid_until || 'Not set'}</span>
                    </div>
                    <div className="text-indigo-700 font-semibold">
                      Next Billing: <span className="font-mono">{selectedSubDetail.next_billing_date || 'None'}</span>
                    </div>
                  </div>
                </div>

                {/* Line Items Table */}
                <div className="space-y-2">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    Agreement Line Items
                  </div>
                  <div className="border border-slate-200 rounded-xl overflow-hidden text-xs">
                    <table className="w-full text-left">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                        <tr>
                          <th className="p-2.5">Product & Variant</th>
                          <th className="p-2.5 text-right">Unit Price</th>
                          <th className="p-2.5 text-center">Qty</th>
                          <th className="p-2.5 text-right">Tax</th>
                          <th className="p-2.5 text-right">Line Total</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {selectedSubDetail.plan_charge && (
                          <tr>
                            <td className="p-2.5">
                              <div className="font-semibold text-slate-900">{selectedSubDetail.plan_name}</div>
                              <div className="text-[11px] text-slate-500">Plan base fee</div>
                            </td>
                            <td className="p-2.5 text-right font-mono text-slate-700">
                              ${Number(selectedSubDetail.plan_charge.unit_price).toFixed(2)}
                            </td>
                            <td className="p-2.5 text-center font-mono text-slate-700">1</td>
                            <td className="p-2.5 text-right text-slate-600">
                              {selectedSubDetail.plan_charge.tax_name
                                ? `${selectedSubDetail.plan_charge.tax_name} ${Number(selectedSubDetail.plan_charge.tax_rate).toFixed(2)}% · $${Number(selectedSubDetail.plan_charge.tax_amount).toFixed(2)}`
                                : '—'}
                            </td>
                            <td className="p-2.5 text-right font-mono font-bold text-slate-900">
                              ${Number(selectedSubDetail.plan_charge.line_total).toFixed(2)}
                            </td>
                          </tr>
                        )}
                        {selectedSubDetail.lines.map((ln) => (
                          <tr key={ln.id}>
                            <td className="p-2.5">
                              <div className="font-semibold text-slate-900">{ln.product_name}</div>
                              {ln.variant_name && (
                                <div className="text-[11px] text-indigo-600 font-medium">
                                  Variant: {ln.variant_name}
                                </div>
                              )}
                            </td>
                            <td className="p-2.5 text-right font-mono text-slate-700">
                              ${Number(ln.unit_price).toFixed(2)}
                            </td>
                            <td className="p-2.5 text-center font-mono text-slate-700">{ln.quantity}</td>
                            <td className="p-2.5 text-right text-slate-600">
                              {ln.tax_rate !== null && ln.tax_rate !== undefined
                                ? `${Number(ln.tax_rate).toFixed(2)}% · $${Number(ln.tax_amount).toFixed(2)}`
                                : '—'}
                            </td>
                            <td className="p-2.5 text-right font-mono font-bold text-slate-900">
                              ${Number(ln.line_total).toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="ml-auto max-w-xs space-y-1.5 p-2 text-xs">
                    <div className="flex justify-between text-slate-600">
                      <span>Subtotal</span>
                      <span className="font-mono">${Number(selectedSubDetail.subtotal_amount).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>Discounts</span>
                      <span className="font-mono">−${Number(selectedSubDetail.discount_amount).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>Tax</span>
                      <span className="font-mono">${Number(selectedSubDetail.tax_amount).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between border-t border-slate-200 pt-2 text-sm font-bold text-slate-900">
                      <span>Total Order Value</span>
                      <span className="font-mono">${Number(selectedSubDetail.total_amount).toFixed(2)}</span>
                    </div>
                    {selectedSubDetail.calculation_warnings.length > 0 && (
                      <div className="rounded-md bg-amber-50 p-2 text-amber-800">
                        {selectedSubDetail.calculation_warnings.map((warning) => <div key={warning}>{warning}</div>)}
                      </div>
                    )}
                  </div>
                </div>

                {/* Traceable Status History Timeline */}
                <div className="space-y-3 pt-2 border-t border-slate-200">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <History className="w-4 h-4 text-indigo-600" />
                    <span>Traceable Status History</span>
                  </div>

                  {selectedSubDetail.audit_history.length === 0 ? (
                    <div className="text-xs text-slate-400 italic">No audit records found.</div>
                  ) : (
                    <div className="space-y-2.5">
                      {selectedSubDetail.audit_history.map((ev) => (
                        <div
                          key={ev.id}
                          className="flex items-start gap-3 text-xs p-2.5 bg-slate-50/80 rounded-lg border border-slate-100"
                        >
                          <div className="w-2 h-2 rounded-full bg-indigo-500 mt-1.5 shrink-0" />
                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-900">{ev.action}</span>
                              <span className="text-[11px] text-slate-400 font-mono">
                                {new Date(ev.timestamp).toLocaleString()}
                              </span>
                            </div>
                            <div className="text-slate-600 mt-0.5">
                              Actor: <span className="font-medium text-slate-800">{ev.actor_name}</span> (
                              {ev.actor_role})
                            </div>
                            {ev.changes && Object.keys(ev.changes).length > 0 && (
                              <div className="text-[11px] text-slate-500 font-mono mt-1 bg-white p-1.5 rounded border border-slate-100">
                                {JSON.stringify(ev.changes)}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ---------------- CREATE QUOTE / SUBSCRIPTION MODAL ---------------- */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-2xl overflow-hidden max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
              <h3 className="font-bold text-slate-900 text-base">Create Quotation or Order</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubscription} className="p-6 space-y-4 overflow-y-auto flex-1">
              {createFormError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                  {createFormError}
                </div>
              )}

              {/* Template Quick Loader */}
              {templates.length > 0 && (
                <div className="p-3 bg-indigo-50/60 rounded-xl border border-indigo-100 space-y-1">
                  <label className="block text-xs font-bold text-indigo-950">
                    Instantiate from Template (Optional)
                  </label>
                  <select
                    value={createForm.template_id}
                    onChange={(e) => handleSelectTemplateInForm(e.target.value)}
                    className="w-full px-3 py-1.5 border border-indigo-200 rounded-lg text-xs bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="">No Template (Build Custom)</option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.validity_days} Days Validity)
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Customer Account *</label>
                  <select
                    value={createForm.customer_account_id}
                    onChange={(e) => setCreateForm({ ...createForm, customer_account_id: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    {customerAccounts.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.company_name} ({c.billing_email})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Subscription Plan *</label>
                  <select
                    value={createForm.plan_id}
                    onChange={(e) => setCreateForm({ ...createForm, plan_id: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    {plans.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} (${Number(p.base_price).toFixed(2)} / {p.cadence})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Start Date *</label>
                  <input
                    type="date"
                    required
                    value={createForm.start_date}
                    onChange={(e) => setCreateForm({ ...createForm, start_date: e.target.value })}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Subscription Expiry</label>
                  <input
                    type="date"
                    value={createForm.expiry_date}
                    onChange={(e) => setCreateForm({ ...createForm, expiry_date: e.target.value })}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Quote Valid Until</label>
                  <input
                    type="date"
                    value={createForm.quote_valid_until}
                    onChange={(e) => setCreateForm({ ...createForm, quote_valid_until: e.target.value })}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Status Mode *</label>
                  <select
                    value={createForm.status}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, status: e.target.value as 'draft' | 'quotation' })
                    }
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs bg-white"
                  >
                    <option value="quotation">Issue Quotation</option>
                    <option value="draft">Save as Draft</option>
                  </select>
                </div>
              </div>

              {/* Line Items Builder */}
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-slate-700">Product Line Items</label>
                  <button
                    type="button"
                    onClick={() => {
                      if (products.length === 0) return;
                      setCreateForm({
                        ...createForm,
                        lines: [
                          ...createForm.lines,
                          { product_id: products[0].id, variant_id: '', quantity: 1 },
                        ],
                      });
                    }}
                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Item
                  </button>
                </div>

                {createForm.lines.map((l, idx) => {
                  const prod = products.find((p) => p.id === l.product_id);
                  const variants = prod?.variants || [];

                  return (
                    <div
                      key={idx}
                      className="grid grid-cols-12 gap-2 p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs items-center"
                    >
                      <div className="col-span-5">
                        <select
                          value={l.product_id}
                          onChange={(e) => {
                            const newLines = [...createForm.lines];
                            newLines[idx].product_id = e.target.value;
                            newLines[idx].variant_id = '';
                            setCreateForm({ ...createForm, lines: newLines });
                          }}
                          className="w-full px-2 py-1.5 border border-slate-300 rounded-lg bg-white text-xs"
                        >
                          {products.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name} (${Number(p.sales_price).toFixed(2)})
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="col-span-4">
                        <select
                          value={l.variant_id}
                          onChange={(e) => {
                            const newLines = [...createForm.lines];
                            newLines[idx].variant_id = e.target.value;
                            setCreateForm({ ...createForm, lines: newLines });
                          }}
                          className="w-full px-2 py-1.5 border border-slate-300 rounded-lg bg-white text-xs"
                        >
                          <option value="">Standard Edition (₹0.00)</option>
                          {variants.map((v) => (
                            <option key={v.id} value={v.id}>
                              {v.name} (+₹{Number(v.price_adjustment).toFixed(2)})
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="col-span-2">
                        <input
                          type="number"
                          min="1"
                          value={l.quantity}
                          onChange={(e) => {
                            const newLines = [...createForm.lines];
                            newLines[idx].quantity = parseInt(e.target.value) || 1;
                            setCreateForm({ ...createForm, lines: newLines });
                          }}
                          className="w-full px-2 py-1.5 border border-slate-300 rounded-lg text-xs text-center font-mono bg-white"
                        />
                      </div>
                      <div className="col-span-1 text-center">
                        <button
                          type="button"
                          onClick={() => {
                            setCreateForm({
                              ...createForm,
                              lines: createForm.lines.filter((_, i) => i !== idx),
                            });
                          }}
                          className="text-slate-400 hover:text-red-600 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createSubmitting}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {createSubmitting ? 'Creating...' : createForm.status === 'quotation' ? 'Issue Quotation' : 'Save Draft'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ---------------- CREATE TEMPLATE MODAL ---------------- */}
      {showTemplateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
              <h3 className="font-bold text-slate-900 text-base">Create Quotation Template</h3>
              <button onClick={() => setShowTemplateModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateTemplate} className="p-6 space-y-4">
              {templateFormError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                  {templateFormError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Template Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Standard Onboarding Package"
                  value={templateForm.name}
                  onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Validity (Days) *</label>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    required
                    value={templateForm.validity_days}
                    onChange={(e) =>
                      setTemplateForm({ ...templateForm, validity_days: parseInt(e.target.value) || 30 })
                    }
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Default Plan</label>
                  <select
                    value={templateForm.default_plan_id}
                    onChange={(e) => setTemplateForm({ ...templateForm, default_plan_id: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="">No Default Plan</option>
                    {plans.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} (${Number(p.base_price).toFixed(2)})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowTemplateModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={templateSubmitting}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {templateSubmitting ? 'Saving...' : 'Save Template'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

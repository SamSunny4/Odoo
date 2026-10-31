import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  api,
  InvoiceApiItem,
  PortalAddonProduct,
  PortalPaymentItem,
  PortalProfile,
  PortalSubscriptionActionPayload,
  SubscriptionApiItem,
} from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { SearchAndFilterBar, FilterOption, SortOption } from '../components/common/SearchAndFilterBar';
import { PaginationControls } from '../components/common/PaginationControls';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import {
  CheckCircle2,
  Download,
  RefreshCw,
  CalendarDays,
  Receipt,
  Building,
  Pause,
  Play,
  RotateCw,
  X,
  Plus,
  Trash2,
  CreditCard,
  Clock3,
} from 'lucide-react';

interface CustomerPortalProps {
  activeTab?: string;
  onNavigate?: (tabKey: string) => void;
}

const SUBSCRIPTION_STATUS_OPTIONS: FilterOption[] = [
  { label: 'Active', value: 'active' },
  { label: 'Quotation', value: 'quotation' },
  { label: 'Confirmed', value: 'confirmed' },
  { label: 'Paused', value: 'paused' },
  { label: 'Closed', value: 'closed' },
  { label: 'Draft', value: 'draft' },
];

const SUBSCRIPTION_SORT_OPTIONS: SortOption[] = [
  { label: 'Newest First', sortBy: 'created_at', sortOrder: 'desc' },
  { label: 'Oldest First', sortBy: 'created_at', sortOrder: 'asc' },
  { label: 'Subscription # (A-Z)', sortBy: 'subscription_number', sortOrder: 'asc' },
  { label: 'Next Billing Date', sortBy: 'next_billing_date', sortOrder: 'asc' },
];

const INVOICE_STATUS_OPTIONS: FilterOption[] = [
  { label: 'Confirmed', value: 'confirmed' },
  { label: 'Paid', value: 'paid' },
  { label: 'Overdue', value: 'overdue' },
  { label: 'Draft', value: 'draft' },
  { label: 'Cancelled', value: 'cancelled' },
];

const INVOICE_SORT_OPTIONS: SortOption[] = [
  { label: 'Issue Date (Newest)', sortBy: 'issue_date', sortOrder: 'desc' },
  { label: 'Issue Date (Oldest)', sortBy: 'issue_date', sortOrder: 'asc' },
  { label: 'Due Date (Earliest)', sortBy: 'due_date', sortOrder: 'asc' },
  { label: 'Total Amount (High to Low)', sortBy: 'total_amount', sortOrder: 'desc' },
  { label: 'Outstanding Balance', sortBy: 'outstanding_balance', sortOrder: 'desc' },
];

type PortalAction = PortalSubscriptionActionPayload['action'];
type PortalAddonLine = NonNullable<PortalSubscriptionActionPayload['lines']>[number];

export const CustomerPortal: React.FC<CustomerPortalProps> = ({
  activeTab = 'portal-subscriptions',
  onNavigate,
}) => {
  const { user } = useAuth();
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Subscriptions Tab State
  const [subscriptions, setSubscriptions] = useState<SubscriptionApiItem[]>([]);
  const [subsLoading, setSubsLoading] = useState<boolean>(true);
  const [subsPage, setSubsPage] = useState<number>(1);
  const [subsPageSize, setSubsPageSize] = useState<number>(5);
  const [subsTotal, setSubsTotal] = useState<number>(0);
  const [subsTotalPages, setSubsTotalPages] = useState<number>(1);
  const [subsSearch, setSubsSearch] = useState<string>('');
  const [subsStatus, setSubsStatus] = useState<string>('all');
  const [subsSort, setSubsSort] = useState<string>('created_at-desc');

  // Invoices Tab State
  const [invoices, setInvoices] = useState<InvoiceApiItem[]>([]);
  const [invsLoading, setInvsLoading] = useState<boolean>(true);
  const [invsPage, setInvsPage] = useState<number>(1);
  const [invsPageSize, setInvsPageSize] = useState<number>(5);
  const [invsTotal, setInvsTotal] = useState<number>(0);
  const [invsTotalPages, setInvsTotalPages] = useState<number>(1);
  const [invsSearch, setInvsSearch] = useState<string>('');
  const [invsStatus, setInvsStatus] = useState<string>('all');
  const [invsSort, setInvsSort] = useState<string>('issue_date-desc');

  // Payment history and self-service controls
  const [payments, setPayments] = useState<PortalPaymentItem[]>([]);
  const [paymentsLoading, setPaymentsLoading] = useState<boolean>(true);
  const [paymentsPage, setPaymentsPage] = useState<number>(1);
  const [paymentsTotal, setPaymentsTotal] = useState<number>(0);
  const [paymentsTotalPages, setPaymentsTotalPages] = useState<number>(1);
  const [addons, setAddons] = useState<PortalAddonProduct[]>([]);
  const [addonTarget, setAddonTarget] = useState<SubscriptionApiItem | null>(null);
  const [addonDraft, setAddonDraft] = useState<PortalAddonLine[]>([]);
  const [pendingAction, setPendingAction] = useState<{
    subscription: SubscriptionApiItem;
    action: PortalAction;
    lines?: PortalAddonLine[];
  } | null>(null);
  const [actionBusy, setActionBusy] = useState<boolean>(false);
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const formatMoney = (value: number | string, currencyCode = profile?.currency || 'USD') => {
    const amount = Number(value);
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency: currencyCode }).format(amount);
    } catch {
      return `${currencyCode} ${amount.toFixed(2)}`;
    }
  };

  const fetchProfile = useCallback(async () => {
    try {
      const prof = await api.getPortalProfile();
      setProfile(prof);
      setIsLive(true);
    } catch {
      // Non-fatal
    }
  }, []);

  const fetchSubscriptions = useCallback(async () => {
    setSubsLoading(true);
    const [sortBy, sortOrder] = subsSort.split('-') as [string, 'asc' | 'desc'];
    try {
      const data = await api.getPortalSubscriptions({
        page: subsPage,
        pageSize: subsPageSize,
        search: subsSearch || undefined,
        status: subsStatus !== 'all' ? subsStatus : undefined,
        sortBy,
        sortOrder,
      });
      setSubscriptions(data.items);
      setSubsTotal(data.total);
      setSubsTotalPages(data.totalPages);
      setIsLive(true);
    } catch (err) {
      setSubscriptions([]);
      setError(err instanceof Error ? err.message : 'Could not load subscriptions.');
    } finally {
      setSubsLoading(false);
    }
  }, [subsPage, subsPageSize, subsSearch, subsStatus, subsSort]);

  const fetchInvoices = useCallback(async () => {
    setInvsLoading(true);
    const [sortBy, sortOrder] = invsSort.split('-') as [string, 'asc' | 'desc'];
    try {
      const data = await api.getPortalInvoices({
        page: invsPage,
        pageSize: invsPageSize,
        search: invsSearch || undefined,
        status: invsStatus !== 'all' ? invsStatus : undefined,
        sortBy,
        sortOrder,
      });
      setInvoices(data.items);
      setInvsTotal(data.total);
      setInvsTotalPages(data.totalPages);
      setIsLive(true);
    } catch (err) {
      setInvoices([]);
      setError(err instanceof Error ? err.message : 'Could not load invoices.');
    } finally {
      setInvsLoading(false);
    }
  }, [invsPage, invsPageSize, invsSearch, invsStatus, invsSort]);

  const fetchPayments = useCallback(async () => {
    setPaymentsLoading(true);
    try {
      const data = await api.getPortalPayments({ page: paymentsPage, pageSize: 10 });
      setPayments(data.items);
      setPaymentsTotal(data.total);
      setPaymentsTotalPages(data.totalPages);
      setIsLive(true);
    } catch (err) {
      setPayments([]);
      setError(err instanceof Error ? err.message : 'Could not load payment history.');
    } finally {
      setPaymentsLoading(false);
    }
  }, [paymentsPage]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile, user?.id]);

  useEffect(() => {
    if (activeTab === 'portal-subscriptions') {
      fetchSubscriptions();
    } else if (activeTab === 'portal-invoices') {
      fetchInvoices();
    } else if (activeTab === 'portal-payments') {
      fetchPayments();
    }
  }, [activeTab, fetchSubscriptions, fetchInvoices, fetchPayments]);

  const handleRefreshAll = () => {
    fetchProfile();
    if (activeTab === 'portal-subscriptions') fetchSubscriptions();
    if (activeTab === 'portal-invoices') fetchInvoices();
    if (activeTab === 'portal-payments') fetchPayments();
  };

  const getTabTitle = () => {
    if (activeTab === 'portal-invoices') return 'My Invoices & Receipts';
    if (activeTab === 'portal-payments') return 'Payment History';
    if (activeTab === 'portal-profile') return 'Company & Billing Profile';
    return 'My Subscriptions';
  };

  const localToday = () => {
    const today = new Date();
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  };

  const openActionConfirmation = (subscription: SubscriptionApiItem, action: PortalAction) => {
    setActionFeedback(null);
    setPendingAction({ subscription, action });
  };

  const openAddonEditor = async (subscription: SubscriptionApiItem) => {
    setActionFeedback(null);
    try {
      const catalog = await api.getPortalAddonCatalog();
      setAddons(catalog);
      setAddonTarget(subscription);
      setAddonDraft(subscription.lines.filter((line) => line.product_is_add_on).map((line) => ({
        product_id: line.product_id,
        product_variant_id: line.product_variant_id || undefined,
        quantity: line.quantity,
      })));
    } catch (err) {
      setActionFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Could not load add-ons.' });
    }
  };

  const addAddonLine = () => {
    if (!addons.length) return;
    setAddonDraft((current) => [...current, { product_id: addons[0].id, quantity: 1 }]);
  };

  const changeAddonProduct = (index: number, productId: string) => {
    setAddonDraft((current) => current.map((line, lineIndex) =>
      lineIndex === index ? { product_id: productId, quantity: line.quantity } : line
    ));
  };

  const confirmSelfServiceAction = async () => {
    if (!pendingAction) return;
    setActionBusy(true);
    try {
      const result = await api.performPortalSubscriptionAction(pendingAction.subscription.id, {
        action: pendingAction.action,
        reason: `Customer portal request by ${user?.email || 'account owner'}`,
        lines: pendingAction.lines,
      });
      setPendingAction(null);
      setAddonTarget(null);
      setActionFeedback({
        type: 'success',
        text: `${result.message}${result.effective_date ? ` Effective ${result.effective_date}.` : ''}`,
      });
      await fetchSubscriptions();
    } catch (err) {
      setActionFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Could not update this subscription.' });
    } finally {
      setActionBusy(false);
    }
  };

  const downloadInvoice = async (invoice: InvoiceApiItem) => {
    setActionFeedback(null);
    try {
      const blob = await api.downloadPortalInvoicePdf(invoice.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${invoice.invoice_number}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setActionFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Could not download invoice.' });
    }
  };

  const actionEffectiveDate = (subscription: SubscriptionApiItem, action: PortalAction) => {
    const today = localToday();
    if (action === 'cancel' && !subscription.plan_allow_early_close) {
      return subscription.expiry_date || subscription.next_billing_date || 'Not available';
    }
    if (action === 'renew') {
      if (!subscription.expiry_date) return today;
      const nextDay = new Date(`${subscription.expiry_date}T12:00:00`);
      nextDay.setDate(nextDay.getDate() + 1);
      return `${nextDay.getFullYear()}-${String(nextDay.getMonth() + 1).padStart(2, '0')}-${String(nextDay.getDate()).padStart(2, '0')}`;
    }
    if (action === 'change_addons') {
      return subscription.next_billing_date && subscription.next_billing_date > today
        ? subscription.next_billing_date
        : today;
    }
    return today;
  };

  const addonDraftSubtotal = addonDraft.reduce((sum, line) => {
    const product = addons.find((item) => item.id === line.product_id);
    const variant = product?.variants.find((item) => item.id === line.product_variant_id);
    return sum + (Number(product?.sales_price || 0) + Number(variant?.price_adjustment || 0)) * line.quantity;
  }, 0);

  return (
    <div className="space-y-6">
      {/* Account Shell Header */}
      <PageHeader
        title={profile?.company_name || user?.companyName || 'Customer Portal'}
        subtitle={`Signed in as ${user?.email || 'Customer'} (Scoped strictly to your company account)`}
        breadcrumbs={[
          { label: 'Customer Portal', tabKey: 'portal-subscriptions' },
          { label: getTabTitle() },
        ]}
        onSelectTab={onNavigate}
        badge={
          <span
            className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
              isLive ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
            }`}
          >
            {isLive ? '● Live Account Data' : 'Connecting...'}
          </span>
        }
        actions={
          <button
            onClick={handleRefreshAll}
            className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
            title="Refresh"
            aria-label="Refresh customer data"
          >
            <RefreshCw className={`w-4 h-4 ${subsLoading || invsLoading || paymentsLoading ? 'animate-spin' : ''}`} />
          </button>
        }
      />

      {error && <ErrorState message={error} onRetry={handleRefreshAll} />}
      {actionFeedback && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${actionFeedback.type === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'}`}>
          {actionFeedback.text}
        </div>
      )}

      {/* Subscriptions Tab */}
      {activeTab === 'portal-subscriptions' && (
        <div className="space-y-4">
          <SearchAndFilterBar
            searchQuery={subsSearch}
            onSearchChange={(q) => {
              setSubsSearch(q);
              setSubsPage(1);
            }}
            searchPlaceholder="Search your subscriptions by #..."
            statusFilter={subsStatus}
            onStatusChange={(value) => {
              setSubsStatus(value);
              setSubsPage(1);
            }}
            statusOptions={SUBSCRIPTION_STATUS_OPTIONS}
            sortValue={subsSort}
            onSortChange={(value) => {
              setSubsSort(value);
              setSubsPage(1);
            }}
            sortOptions={SUBSCRIPTION_SORT_OPTIONS}
            onReset={() => {
              setSubsSearch('');
              setSubsStatus('all');
              setSubsSort('created_at-desc');
              setSubsPage(1);
            }}
          />

          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            {subsLoading ? (
              <LoadingState message="Loading your subscriptions..." rows={3} />
            ) : subscriptions.length === 0 ? (
              <EmptyState
                title="No subscriptions found"
                description="There are currently no active subscriptions associated with your account."
                icon={<CalendarDays className="w-6 h-6" />}
              />
            ) : (
              <div className="divide-y divide-slate-200">
                {subscriptions.map((sub) => (
                  <div
                    key={sub.id}
                    className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-50/60 transition"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono font-semibold text-indigo-700">
                          {sub.subscription_number}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${sub.status === 'active' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}`}>
                          {sub.status}
                        </span>
                        {sub.cancel_at_period_end && (
                          <span className="text-[11px] px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-800">
                            Cancellation scheduled
                          </span>
                        )}
                      </div>
                      <h3 className="text-base font-bold text-slate-900 mt-1">{sub.plan_name}{sub.plan_cadence ? <span className="ml-2 text-xs font-medium text-slate-500 capitalize">{sub.plan_cadence}</span> : null}</h3>
                      <div className="text-xs text-slate-500 mt-2 flex items-center gap-4 flex-wrap">
                        <span>
                          Renews on: <strong>{sub.next_billing_date || 'Next Cycle'}</strong>
                        </span>
                        <span>
                          Amount: <strong>{formatMoney(sub.total_amount)}</strong>
                        </span>
                        {sub.expiry_date && <span>Ends: <strong>{sub.expiry_date}</strong></span>}
                      </div>
                      {(sub.plan_charge || sub.lines.length > 0) && (
                        <div className="mt-3 max-w-2xl rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                          {sub.plan_charge && (
                            <div className="flex flex-wrap justify-between gap-x-6 gap-y-1 border-b border-slate-200 pb-1.5">
                              <span>{sub.plan_name} plan fee</span>
                              <span>{formatMoney(sub.plan_charge.line_total)}</span>
                            </div>
                          )}
                          {sub.lines.map((line) => (
                            <div key={line.id} className="flex flex-wrap justify-between gap-x-6 gap-y-1 pt-1.5">
                              <span>{line.product_name || 'Product'}{line.variant_name ? ` · ${line.variant_name}` : ''} × {line.quantity}</span>
                              <span>{formatMoney(line.line_total)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 self-start md:self-auto">
                      {sub.status === 'active' && sub.plan_allow_pause && (
                        <button onClick={() => openActionConfirmation(sub, 'pause')} className="px-3 py-1.5 text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 rounded-lg transition inline-flex items-center gap-1">
                          <Pause className="w-3.5 h-3.5" /> Pause
                        </button>
                      )}
                      {sub.status === 'paused' && (
                        <button onClick={() => openActionConfirmation(sub, 'resume')} className="px-3 py-1.5 text-xs font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition inline-flex items-center gap-1">
                          <Play className="w-3.5 h-3.5" /> Resume
                        </button>
                      )}
                      {sub.status === 'active' && sub.plan_allow_renewal && (
                        <button onClick={() => openActionConfirmation(sub, 'renew')} className="px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition inline-flex items-center gap-1">
                          <RotateCw className="w-3.5 h-3.5" /> Renew
                        </button>
                      )}
                      {sub.status === 'active' && (
                        <button onClick={() => openAddonEditor(sub)} className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition">
                          Manage Add-ons
                        </button>
                      )}
                      {sub.status !== 'closed' && !sub.cancel_at_period_end && (
                        <button
                          onClick={() => openActionConfirmation(sub, 'cancel')}
                          disabled={sub.status === 'active' && !sub.plan_allow_early_close && !sub.expiry_date}
                          title={sub.status === 'active' && !sub.plan_allow_early_close && !sub.expiry_date ? 'Ask your account team to set a term end date before scheduling cancellation.' : undefined}
                          className="px-3 py-1.5 text-xs font-semibold text-red-700 bg-red-50 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50 rounded-lg transition inline-flex items-center gap-1"
                        >
                          <X className="w-3.5 h-3.5" />
                          {sub.status === 'active' && !sub.plan_allow_early_close && sub.expiry_date ? 'Cancel at term end' : 'Cancel'}
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                <PaginationControls
                  page={subsPage}
                  pageSize={subsPageSize}
                  total={subsTotal}
                  totalPages={subsTotalPages}
                  onPageChange={setSubsPage}
                  onPageSizeChange={(sz) => {
                    setSubsPageSize(sz);
                    setSubsPage(1);
                  }}
                  pageSizeOptions={[5, 10, 20]}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Invoices Tab */}
      {activeTab === 'portal-invoices' && (
        <div className="space-y-4">
          <SearchAndFilterBar
            searchQuery={invsSearch}
            onSearchChange={(q) => {
              setInvsSearch(q);
              setInvsPage(1);
            }}
            searchPlaceholder="Search your invoices by #..."
            statusFilter={invsStatus}
            onStatusChange={(value) => {
              setInvsStatus(value);
              setInvsPage(1);
            }}
            statusOptions={INVOICE_STATUS_OPTIONS}
            sortValue={invsSort}
            onSortChange={(value) => {
              setInvsSort(value);
              setInvsPage(1);
            }}
            sortOptions={INVOICE_SORT_OPTIONS}
            onReset={() => {
              setInvsSearch('');
              setInvsStatus('all');
              setInvsSort('issue_date-desc');
              setInvsPage(1);
            }}
          />

          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            {invsLoading ? (
              <LoadingState message="Loading your billing documents..." rows={3} />
            ) : invoices.length === 0 ? (
              <EmptyState
                title="No invoices found"
                description="There are no billing documents or invoices for your account."
                icon={<Receipt className="w-6 h-6" />}
              />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-sm min-w-[550px]">
                    <thead>
                      <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                        <th className="py-3 px-4">Invoice #</th>
                        <th className="py-3 px-4">Period</th>
                        <th className="py-3 px-4 text-right">Amount</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4 text-right">Receipt / PDF</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {invoices.map((inv) => (
                        <tr key={inv.id} className="hover:bg-slate-50/60 transition">
                          <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">
                            {inv.invoice_number}
                          </td>
                          <td className="py-3.5 px-4 text-xs text-slate-600">
                            {inv.billing_period_start} – {inv.billing_period_end}
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">
                            {formatMoney(inv.total_amount, inv.currency || profile?.currency || 'USD')}
                          </td>
                          <td className="py-3.5 px-4">
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 capitalize">
                              <CheckCircle2 className="w-3 h-3" />
                              {inv.status}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            <button
                              onClick={() => downloadInvoice(inv)}
                              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1 transition"
                            >
                              <Download className="w-3.5 h-3.5" />
                              PDF
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <PaginationControls
                  page={invsPage}
                  pageSize={invsPageSize}
                  total={invsTotal}
                  totalPages={invsTotalPages}
                  onPageChange={setInvsPage}
                  onPageSizeChange={(sz) => {
                    setInvsPageSize(sz);
                    setInvsPage(1);
                  }}
                  pageSizeOptions={[5, 10, 20]}
                />
              </>
            )}
          </div>
        </div>
      )}

      {/* Payment History Tab */}
      {activeTab === 'portal-payments' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          {paymentsLoading ? (
            <LoadingState message="Loading your payment history..." rows={4} />
          ) : payments.length === 0 ? (
            <EmptyState
              title="No payments recorded"
              description="Payments allocated to your account invoices will appear here."
              icon={<CreditCard className="w-6 h-6" />}
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[620px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-600">
                      <th className="px-4 py-3">Invoice</th>
                      <th className="px-4 py-3">Payment Date</th>
                      <th className="px-4 py-3">Method / Reference</th>
                      <th className="px-4 py-3 text-right">Amount</th>
                      <th className="px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {payments.map((payment) => (
                      <tr key={payment.id} className="hover:bg-slate-50/60">
                        <td className="px-4 py-3 font-mono font-semibold text-indigo-700">{payment.invoice_number}</td>
                        <td className="px-4 py-3 text-slate-700">{payment.payment_date}</td>
                        <td className="px-4 py-3">
                          <div className="capitalize text-slate-800">{payment.payment_method.replace(/_/g, ' ')}</div>
                          <div className="text-xs text-slate-500">{payment.reference_note || 'No reference'}</div>
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-semibold text-slate-900">
                          {payment.currency} {Number(payment.amount).toFixed(2)}
                          {Number(payment.refunded_amount) > 0 && (
                            <div className="text-xs font-normal text-amber-700">
                              Refunded {payment.currency} {Number(payment.refunded_amount).toFixed(2)} · Net {payment.currency} {Number(payment.net_amount).toFixed(2)}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${payment.is_reversed || Number(payment.refunded_amount) > 0 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}`}>
                            {payment.is_reversed ? 'Reversed' : Number(payment.refunded_amount) > 0 ? 'Partially refunded' : 'Received'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <PaginationControls
                page={paymentsPage}
                pageSize={10}
                total={paymentsTotal}
                totalPages={paymentsTotalPages}
                onPageChange={setPaymentsPage}
                onPageSizeChange={() => undefined}
                pageSizeOptions={[10]}
              />
            </>
          )}
        </div>
      )}

      {/* Profile Tab */}
      {activeTab === 'portal-profile' && profile && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs max-w-2xl space-y-5">
          <div className="flex items-center gap-3 pb-3 border-b border-slate-200">
            <Building className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Company Billing Profile</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Company Name</span>
              <div className="font-medium text-slate-800">{profile.company_name}</div>
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Tax ID / VAT</span>
              <div className="font-medium text-slate-800">{profile.tax_id || 'None'}</div>
            </div>
            <div className="sm:col-span-2">
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Billing Address</span>
              <div className="font-medium text-slate-800">
                {profile.billing_address || 'No billing address on file'}
              </div>
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Billing Currency</span>
              <div className="font-medium text-slate-800">{profile.currency}</div>
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Registered Email</span>
              <div className="font-medium text-slate-800">{profile.billing_email}</div>
            </div>
          </div>
        </div>
      )}

      {addonTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <h2 className="font-bold text-slate-900">Manage add-ons</h2>
                <p className="mt-1 text-xs text-slate-500">Changes apply to the next billing date.</p>
              </div>
              <button onClick={() => setAddonTarget(null)} aria-label="Close add-ons" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto p-6">
              {addonDraft.length === 0 && (
                <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">No add-on lines selected. You can add an active product below.</div>
              )}
              {addonDraft.map((line, index) => {
                const product = addons.find((item) => item.id === line.product_id);
                const selectedVariant = product?.variants.find((variant) => variant.id === line.product_variant_id);
                return (
                  <div key={`${line.product_id}-${index}`} className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 p-4 sm:grid-cols-[1fr_1fr_100px_40px]">
                    <label className="text-xs font-semibold text-slate-600">
                      Product
                      <select value={line.product_id} onChange={(event) => changeAddonProduct(index, event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm font-normal text-slate-800">
                        {addons.map((item) => <option key={item.id} value={item.id}>{item.name} · {formatMoney(item.sales_price)}</option>)}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-600">
                      Variant
                      <select value={line.product_variant_id || ''} onChange={(event) => setAddonDraft((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, product_variant_id: event.target.value || undefined } : item))} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm font-normal text-slate-800">
                        <option value="">Standard</option>
                        {product?.variants.map((variant) => <option key={variant.id} value={variant.id}>{variant.name} (+{formatMoney(variant.price_adjustment)})</option>)}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-600">
                      Quantity
                      <input type="number" min={1} max={10000} value={line.quantity} onChange={(event) => setAddonDraft((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, quantity: Math.max(1, Number(event.target.value)) } : item))} className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-2 text-sm font-normal" />
                    </label>
                    <button onClick={() => setAddonDraft((current) => current.filter((_, itemIndex) => itemIndex !== index))} aria-label="Remove add-on" className="mt-5 rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600">
                      <Trash2 className="h-4 w-4" />
                    </button>
                    {selectedVariant && <div className="sm:col-span-4 -mt-2 text-[11px] text-slate-500">Variant price adjustment: +{formatMoney(selectedVariant.price_adjustment)} per unit</div>}
                  </div>
                );
              })}
              <button onClick={addAddonLine} disabled={addons.length === 0} className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 px-3 py-2 text-xs font-semibold text-indigo-700 hover:bg-indigo-50 disabled:opacity-50">
                <Plus className="h-3.5 w-3.5" /> Add product
              </button>
              <div className="flex items-center justify-between rounded-lg border border-indigo-100 bg-indigo-50 px-4 py-3 text-sm">
                <span className="text-slate-700">Selected product lines per billing cycle <span className="block text-xs text-slate-500">Before tax and discounts</span></span>
                <strong className="text-indigo-800">{formatMoney(addonDraftSubtotal)}</strong>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-4">
              <button onClick={() => setAddonTarget(null)} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-200">Keep current</button>
              <button onClick={() => { setPendingAction({ subscription: addonTarget, action: 'change_addons', lines: addonDraft }); setAddonTarget(null); }} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">Review changes</button>
            </div>
          </div>
        </div>
      )}

      {pendingAction && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Confirm subscription change</h2>
                <p className="mt-1 text-sm text-slate-600">{pendingAction.subscription.subscription_number} · {pendingAction.subscription.plan_name}</p>
              </div>
              <button onClick={() => setPendingAction(null)} aria-label="Close confirmation" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X className="h-4 w-4" /></button>
            </div>
            <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
              <div className="font-semibold capitalize text-slate-900">{pendingAction.action.replace(/_/g, ' ')}</div>
              <div className="mt-2 flex items-center gap-2 text-xs text-slate-600">
                <Clock3 className="h-3.5 w-3.5" /> Effective date: <strong>{actionEffectiveDate(pendingAction.subscription, pendingAction.action)}</strong>
              </div>
              {pendingAction.action === 'cancel' && !pendingAction.subscription.plan_allow_early_close && (
                <p className="mt-3 text-xs text-amber-800">Your plan does not permit early cancellation. Service remains active until the current term ends.</p>
              )}
              {pendingAction.action === 'renew' && (
                <p className="mt-3 text-xs">The end date will extend by one billing period under your current plan.</p>
              )}
              {pendingAction.action === 'change_addons' && (
                <>
                  <ul className="mt-3 list-inside list-disc space-y-1 text-xs">
                    {(pendingAction.lines || []).map((line, index) => {
                      const product = addons.find((item) => item.id === line.product_id);
                      const variant = product?.variants.find((item) => item.id === line.product_variant_id);
                      return <li key={`${line.product_id}-${index}`}>{product?.name || 'Product'}{variant ? ` · ${variant.name}` : ''} × {line.quantity}</li>;
                    })}
                    {(pendingAction.lines || []).length === 0 && <li>Remove all product add-ons</li>}
                  </ul>
                  <div className="mt-3 border-t border-slate-200 pt-3 text-xs text-slate-600">Next product-line subtotal before tax and discounts: <strong>{formatMoney(addonDraftSubtotal)}</strong></div>
                </>
              )}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button disabled={actionBusy} onClick={() => setPendingAction(null)} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">Go back</button>
              <button disabled={actionBusy} onClick={confirmSelfServiceAction} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60">
                {actionBusy ? 'Saving…' : 'Confirm change'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

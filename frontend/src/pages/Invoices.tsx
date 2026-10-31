import React, { useEffect, useState, useCallback } from 'react';
import {
  api,
  InvoiceApiItem,
  InvoiceDetailApiItem,
  SubscriptionApiItem,
  PaymentApiItem,
  CollectionQueueSummary,
} from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { SearchAndFilterBar, FilterOption, SortOption } from '../components/common/SearchAndFilterBar';
import { PaginationControls } from '../components/common/PaginationControls';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { AlertBanner } from '../components/common/AlertBanner';
import { Modal } from '../components/common/Modal';
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  CreditCard,
  RefreshCw,
  XCircle,
  Eye,
  Printer,
  Send,
  Plus,
  Layers,
  History,
  X,
  ChevronRight,
  FileText,
  RotateCcw,
  BellRing,
  AlertCircle,
  Building,
} from 'lucide-react';

const STATUS_OPTIONS: FilterOption[] = [
  { label: 'Confirmed (Open)', value: 'confirmed' },
  { label: 'Partially Paid', value: 'partially_paid' },
  { label: 'Paid', value: 'paid' },
  { label: 'Overdue', value: 'overdue' },
  { label: 'Outstanding (All Unpaid)', value: 'outstanding' },
  { label: 'Draft', value: 'draft' },
  { label: 'Canceled', value: 'cancelled' },
];

const SORT_OPTIONS: SortOption[] = [
  { label: 'Issue Date (Newest)', sortBy: 'issue_date', sortOrder: 'desc' },
  { label: 'Issue Date (Oldest)', sortBy: 'issue_date', sortOrder: 'asc' },
  { label: 'Due Date (Earliest)', sortBy: 'due_date', sortOrder: 'asc' },
  { label: 'Total Amount (High to Low)', sortBy: 'total_amount', sortOrder: 'desc' },
  { label: 'Outstanding Balance', sortBy: 'outstanding_balance', sortOrder: 'desc' },
];

interface InvoicesProps {
  onNavigate?: (tabKey: string) => void;
}

export const Invoices: React.FC<InvoicesProps> = () => {
  // Main Navigation Mode
  const [mainTab, setMainTab] = useState<'invoices' | 'payments' | 'collections'>('invoices');

  // Invoices State
  const [invoices, setInvoices] = useState<InvoiceApiItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Pagination & Filters State (Invoices)
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortValue, setSortValue] = useState<string>('issue_date-desc');

  // Payments Ledger State
  const [payments, setPayments] = useState<PaymentApiItem[]>([]);
  const [paymentsLoading, setPaymentsLoading] = useState<boolean>(false);
  const [paymentsTotal, setPaymentsTotal] = useState<number>(0);
  const [paymentsPage, setPaymentsPage] = useState<number>(1);
  const [paymentsPageSize, setPaymentsPageSize] = useState<number>(10);
  const [paymentsTotalPages, setPaymentsTotalPages] = useState<number>(1);
  const [paymentsSearch, setPaymentsSearch] = useState<string>('');
  const [paymentsMethodFilter, setPaymentsMethodFilter] = useState<string>('all');
  const [paymentsReversalFilter, setPaymentsReversalFilter] = useState<string>('all');

  // Collection Queue State
  const [collectionQueue, setCollectionQueue] = useState<CollectionQueueSummary | null>(null);
  const [collectionsLoading, setCollectionsLoading] = useState<boolean>(false);
  const [collectionsSearch, setCollectionsSearch] = useState<string>('');
  const [collectionsAgingFilter, setCollectionsAgingFilter] = useState<string>('all');
  const [collectionsSortBy, setCollectionsSortBy] = useState<string>('days_overdue');
  const [remindingInvoiceId, setRemindingInvoiceId] = useState<string | null>(null);

  // Detail Drawer State
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceDetailApiItem | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

  // Payment Modal State
  const [paymentModalInvoice, setPaymentModalInvoice] = useState<InvoiceApiItem | null>(null);
  const [paymentAmount, setPaymentAmount] = useState<string>('');
  const [paymentMethod, setPaymentMethod] = useState<string>('bank_transfer');
  const [paymentNote, setPaymentNote] = useState<string>('');
  const [paymentSubmitting, setPaymentSubmitting] = useState<boolean>(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  // Reversal / Refund Modal State
  const [reversalModalPayment, setReversalModalPayment] = useState<PaymentApiItem | null>(null);
  const [reversalReason, setReversalReason] = useState<string>('');
  const [reversalAmount, setReversalAmount] = useState<string>('');
  const [reversalSubmitting, setReversalSubmitting] = useState<boolean>(false);
  const [reversalError, setReversalError] = useState<string | null>(null);

  // Cancel Modal State
  const [cancelModalInvoice, setCancelModalInvoice] = useState<InvoiceApiItem | null>(null);
  const [cancelReason, setCancelReason] = useState<string>('');
  const [cancelSubmitting, setCancelSubmitting] = useState<boolean>(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  // Generate Draft Modal State
  const [showGenerateModal, setShowGenerateModal] = useState<boolean>(false);
  const [activeSubscriptions, setActiveSubscriptions] = useState<SubscriptionApiItem[]>([]);
  const [selectedSubId, setSelectedSubId] = useState<string>('');
  const [periodStart, setPeriodStart] = useState<string>('');
  const [periodEnd, setPeriodEnd] = useState<string>('');
  const [createAsDraft, setCreateAsDraft] = useState<boolean>(true);
  const [generatingDraft, setGeneratingDraft] = useState<boolean>(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // 1. Fetch Invoices
  const fetchInvoices = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [sortBy, sortOrder] = sortValue.split('-') as [string, 'asc' | 'desc'];

    try {
      const data = await api.getInvoices({
        page,
        pageSize,
        search: searchQuery || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        sortBy,
        sortOrder,
      });

      setInvoices(data.items);
      setTotal(data.total);
      setTotalPages(data.totalPages);
      setIsLive(true);
    } catch (reason) {
      setInvoices([]);
      setIsLive(false);
      setError(reason instanceof Error ? reason.message : 'Could not load invoices.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, searchQuery, statusFilter, sortValue]);

  // 2. Fetch Payments Ledger
  const fetchPayments = useCallback(async () => {
    setPaymentsLoading(true);
    try {
      const params: Record<string, unknown> = {
        page: paymentsPage,
        pageSize: paymentsPageSize,
        search: paymentsSearch || undefined,
      };
      if (paymentsMethodFilter !== 'all') {
        params.payment_method = paymentsMethodFilter;
      }
      if (paymentsReversalFilter === 'active') {
        params.is_reversed = false;
      } else if (paymentsReversalFilter === 'reversed') {
        params.is_reversed = true;
      }

      const data = await api.getPayments(params);
      setPayments(data.items);
      setPaymentsTotal(data.total);
      setPaymentsTotalPages(data.totalPages);
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to load payments ledger.' });
    } finally {
      setPaymentsLoading(false);
    }
  }, [paymentsPage, paymentsPageSize, paymentsSearch, paymentsMethodFilter, paymentsReversalFilter]);

  // 3. Fetch Collection Queue
  const fetchCollections = useCallback(async () => {
    setCollectionsLoading(true);
    try {
      const data = await api.getCollectionQueue({
        search: collectionsSearch || undefined,
        aging_bucket: collectionsAgingFilter !== 'all' ? collectionsAgingFilter : undefined,
        sort_by: collectionsSortBy,
        sort_order: 'desc',
      });
      setCollectionQueue(data);
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to load collection queue.' });
    } finally {
      setCollectionsLoading(false);
    }
  }, [collectionsSearch, collectionsAgingFilter, collectionsSortBy]);

  useEffect(() => {
    if (mainTab === 'invoices') {
      fetchInvoices();
    } else if (mainTab === 'payments') {
      fetchPayments();
    } else if (mainTab === 'collections') {
      fetchCollections();
    }
  }, [mainTab, fetchInvoices, fetchPayments, fetchCollections]);

  const openInvoiceDetail = async (invoiceId: string) => {
    setDetailLoading(true);
    try {
      const detail = await api.getInvoice(invoiceId);
      setSelectedInvoice(detail);
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to load invoice details.' });
    } finally {
      setDetailLoading(false);
    }
  };

  const handleOpenPayment = (inv: InvoiceApiItem | { id: string; invoice_number: string; customer_name: string; total_amount: number | string; paid_amount: number | string; currency: string }) => {
    const balance = Number(inv.total_amount) - Number(inv.paid_amount);
    setPaymentModalInvoice(inv as InvoiceApiItem);
    setPaymentAmount(balance > 0 ? balance.toFixed(2) : '0.00');
    setPaymentMethod('bank_transfer');
    setPaymentNote('Payment recorded via dashboard');
    setPaymentError(null);
  };

  const handleRecordPaymentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!paymentModalInvoice) return;

    const amountNum = parseFloat(paymentAmount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setPaymentError('Please enter a valid positive payment amount.');
      return;
    }

    setPaymentSubmitting(true);
    setPaymentError(null);

    try {
      await api.recordPayment({
        invoice_id: paymentModalInvoice.id,
        amount: amountNum,
        payment_method: paymentMethod,
        payment_date: new Date().toISOString().split('T')[0],
        reference_note: paymentNote || undefined,
      });

      setFeedback({
        type: 'success',
        message: `Payment of ₹${amountNum.toFixed(2)} recorded successfully against invoice ${paymentModalInvoice.invoice_number}.`,
      });
      setPaymentModalInvoice(null);
      fetchInvoices();
      if (mainTab === 'payments') fetchPayments();
      if (mainTab === 'collections') fetchCollections();
      if (selectedInvoice && selectedInvoice.id === paymentModalInvoice.id) {
        openInvoiceDetail(selectedInvoice.id);
      }
    } catch (err) {
      setPaymentError(err instanceof Error ? err.message : 'Failed to record payment.');
    } finally {
      setPaymentSubmitting(false);
    }
  };

  const handleOpenReversal = (payment: PaymentApiItem) => {
    const reversed = (payment.reversals || (payment.reversal ? [payment.reversal] : []))
      .reduce((sum, item) => sum + Number(item.reversal_amount), 0);
    const remaining = Math.max(0, Number(payment.amount) - reversed);
    setReversalModalPayment(payment);
    setReversalReason('');
    setReversalAmount(remaining.toFixed(2));
    setReversalError(null);
  };

  const handleReversalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reversalModalPayment) return;

    if (!reversalReason.trim() || reversalReason.trim().length < 3) {
      setReversalError('Please provide a descriptive audit reason (min 3 characters).');
      return;
    }

    const revAmountNum = parseFloat(reversalAmount);
    if (isNaN(revAmountNum) || revAmountNum <= 0) {
      setReversalError('Please enter a valid positive reversal amount.');
      return;
    }

    setReversalSubmitting(true);
    setReversalError(null);

    try {
      await api.reversePayment(reversalModalPayment.id, reversalReason.trim(), revAmountNum);
      setFeedback({
        type: 'success',
        message: `Payment reversal of ₹${revAmountNum.toFixed(2)} recorded and invoice balance adjusted.`,
      });
      setReversalModalPayment(null);
      fetchInvoices();
      fetchPayments();
      if (mainTab === 'collections') fetchCollections();
      if (selectedInvoice && selectedInvoice.id === reversalModalPayment.invoice_id) {
        openInvoiceDetail(selectedInvoice.id);
      }
    } catch (err) {
      setReversalError(err instanceof Error ? err.message : 'Failed to process payment reversal.');
    } finally {
      setReversalSubmitting(false);
    }
  };

  const handleSendCollectionReminder = async (invoiceId: string, invoiceNumber: string) => {
    setRemindingInvoiceId(invoiceId);
    try {
      await api.sendCollectionReminder(invoiceId);
      setFeedback({
        type: 'success',
        message: `Overdue payment reminder dispatched for invoice ${invoiceNumber} via outbox.`,
      });
      fetchCollections();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to send overdue reminder.',
      });
    } finally {
      setRemindingInvoiceId(null);
    }
  };

  const handleConfirmInvoice = async (invoiceId: string) => {
    try {
      await api.confirmInvoice(invoiceId);
      setFeedback({ type: 'success', message: 'Invoice confirmed and issued.' });
      fetchInvoices();
      if (selectedInvoice?.id === invoiceId) openInvoiceDetail(invoiceId);
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to confirm invoice.' });
    }
  };

  const handleSendInvoice = async (invoiceId: string) => {
    try {
      await api.sendInvoice(invoiceId);
      setFeedback({ type: 'success', message: 'Invoice sent to customer via durable outbox.' });
      fetchInvoices();
      if (selectedInvoice?.id === invoiceId) openInvoiceDetail(invoiceId);
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to send invoice.' });
    }
  };

  const handleOpenCancelModal = (inv: InvoiceApiItem) => {
    setCancelModalInvoice(inv);
    setCancelReason('');
    setCancelError(null);
  };

  const handleCancelSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelModalInvoice || !cancelReason.trim()) return;

    setCancelSubmitting(true);
    setCancelError(null);
    try {
      await api.cancelInvoice(cancelModalInvoice.id, cancelReason.trim());
      setFeedback({ type: 'success', message: `Invoice ${cancelModalInvoice.invoice_number} cancelled.` });
      setCancelModalInvoice(null);
      fetchInvoices();
      if (selectedInvoice?.id === cancelModalInvoice.id) openInvoiceDetail(cancelModalInvoice.id);
    } catch (err) {
      setCancelError(err instanceof Error ? err.message : 'Failed to cancel invoice.');
    } finally {
      setCancelSubmitting(false);
    }
  };

  const handleOpenGenerateModal = async () => {
    setShowGenerateModal(true);
    setGenerateError(null);
    try {
      const subs = await api.getSubscriptions({ pageSize: 50, status: 'active' });
      setActiveSubscriptions(subs.items);
      if (subs.items.length > 0) {
        setSelectedSubId(subs.items[0].id);
      }
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : 'Failed to fetch active subscriptions.');
    }
  };

  const handleGenerateInvoiceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSubId) return;

    setGeneratingDraft(true);
    setGenerateError(null);

    try {
      const generated = await api.generateDraftInvoice({
        subscription_id: selectedSubId,
        billing_period_start: periodStart || undefined,
        billing_period_end: periodEnd || undefined,
        as_draft: createAsDraft,
      });

      setFeedback({
        type: 'success',
        message: `Invoice ${generated.invoice_number} generated (${createAsDraft ? 'Draft' : 'Confirmed'}).`,
      });
      setShowGenerateModal(false);
      fetchInvoices();
      openInvoiceDetail(generated.id);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : 'Failed to generate invoice.');
    } finally {
      setGeneratingDraft(false);
    }
  };

  const handleResetFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setSortValue('issue_date-desc');
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Invoices & Payments"
        subtitle="Create invoices, record customer payments and refunds, and track overdue balances."
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
              onClick={handleOpenGenerateModal}
              className="px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 flex items-center gap-1.5 shadow-xs transition"
            >
              <Plus className="w-4 h-4" />
              Generate Draft Invoice
            </button>
            <button
              onClick={() => {
                if (mainTab === 'invoices') fetchInvoices();
                else if (mainTab === 'payments') fetchPayments();
                else fetchCollections();
              }}
              className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
              title="Refresh"
              aria-label="Refresh data"
            >
              <RefreshCw className={`w-4 h-4 ${loading || paymentsLoading || collectionsLoading ? 'animate-spin' : ''}`} />
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

      {error && <ErrorState message={error} onRetry={fetchInvoices} />}

      {/* High-Agency Navigation Tabs */}
      <div className="flex border-b border-slate-200 space-x-6 text-sm font-medium">
        <button
          onClick={() => setMainTab('invoices')}
          className={`pb-3 px-1 border-b-2 flex items-center gap-2 transition ${
            mainTab === 'invoices'
              ? 'border-indigo-600 text-indigo-700 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Invoices</span>
          <span className="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded-full font-mono">{total}</span>
        </button>

        <button
          onClick={() => setMainTab('payments')}
          className={`pb-3 px-1 border-b-2 flex items-center gap-2 transition ${
            mainTab === 'payments'
              ? 'border-indigo-600 text-indigo-700 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <CreditCard className="w-4 h-4" />
          <span>Payments Ledger</span>
          {paymentsTotal > 0 && (
            <span className="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded-full font-mono">{paymentsTotal}</span>
          )}
        </button>

        <button
          onClick={() => setMainTab('collections')}
          className={`pb-3 px-1 border-b-2 flex items-center gap-2 transition ${
            mainTab === 'collections'
              ? 'border-indigo-600 text-indigo-700 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Clock className="w-4 h-4 text-amber-600" />
          <span>Collection Queue</span>
          {collectionQueue?.total_overdue_invoices ? (
            <span className="bg-amber-100 text-amber-800 text-xs px-2 py-0.5 rounded-full font-semibold">
              {collectionQueue.total_overdue_invoices}
            </span>
          ) : null}
        </button>
      </div>

      {/* TAB 1: INVOICES LIST */}
      {mainTab === 'invoices' && (
        <div className="space-y-4">
          <SearchAndFilterBar
            searchQuery={searchQuery}
            onSearchChange={(q) => {
              setSearchQuery(q);
              setPage(1);
            }}
            searchPlaceholder="Search by invoice # or customer name..."
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
            onReset={handleResetFilters}
          />

          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            {loading ? (
              <LoadingState message="Loading invoices from server..." rows={5} />
            ) : invoices.length === 0 ? (
              <EmptyState
                title="No invoices found"
                description="There are no billing documents matching your search or filters."
                action={{ label: 'Clear Filters', onClick: handleResetFilters }}
              />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-sm min-w-[850px]">
                    <thead>
                      <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                        <th className="py-3 px-4">Invoice #</th>
                        <th className="py-3 px-4">Customer</th>
                        <th className="py-3 px-4">Period</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4 text-right">Total</th>
                        <th className="py-3 px-4 text-right">Paid</th>
                        <th className="py-3 px-4 text-right">Balance</th>
                        <th className="py-3 px-4">Due Date</th>
                        <th className="py-3 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {invoices.map((inv) => {
                        const balance = Number(inv.total_amount) - Number(inv.paid_amount);
                        const isPartiallyPaid = inv.status === 'confirmed' && Number(inv.paid_amount) > 0 && balance > 0;
                        return (
                          <tr key={inv.id} className="hover:bg-slate-50/60 transition">
                            <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">
                              <button
                                onClick={() => openInvoiceDetail(inv.id)}
                                className="hover:underline flex items-center gap-1 font-mono"
                              >
                                {inv.invoice_number}
                              </button>
                            </td>
                            <td className="py-3.5 px-4 font-medium text-slate-900">{inv.customer_name}</td>
                            <td className="py-3.5 px-4 text-xs text-slate-500 whitespace-nowrap">
                              {inv.billing_period_start} → {inv.billing_period_end}
                            </td>
                            <td className="py-3.5 px-4">
                              {isPartiallyPaid ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                                  <Clock className="w-3 h-3 text-amber-600" />
                                  Part-Paid (₹${Number(inv.paid_amount).toFixed(2)})
                                </span>
                              ) : inv.is_overdue && inv.status === 'confirmed' ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800">
                                  <AlertTriangle className="w-3 h-3" />
                                  Overdue
                                </span>
                              ) : inv.status === 'paid' ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                                  <CheckCircle2 className="w-3 h-3" />
                                  Paid
                                </span>
                              ) : inv.status === 'confirmed' ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
                                  <Clock className="w-3 h-3" />
                                  Confirmed (Open)
                                </span>
                              ) : inv.status === 'cancelled' ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">
                                  <XCircle className="w-3 h-3" />
                                  Cancelled
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                                  Draft
                                </span>
                              )}
                            </td>
                            <td className="py-3.5 px-4 text-right font-mono font-medium text-slate-900">
                              ${Number(inv.total_amount).toFixed(2)}
                            </td>
                            <td className="py-3.5 px-4 text-right font-mono text-emerald-600">
                              ${Number(inv.paid_amount).toFixed(2)}
                            </td>
                            <td className="py-3.5 px-4 text-right font-mono font-semibold">
                              <span className={balance > 0 ? 'text-red-600' : 'text-slate-400'}>
                                ${balance.toFixed(2)}
                              </span>
                            </td>
                            <td className="py-3.5 px-4 text-xs text-slate-600 whitespace-nowrap">
                              {inv.due_date}
                            </td>
                            <td className="py-3.5 px-4 text-right space-x-1 whitespace-nowrap">
                              <button
                                onClick={() => openInvoiceDetail(inv.id)}
                                className="p-1.5 text-slate-500 hover:text-indigo-600 rounded-md hover:bg-slate-100 transition"
                                title="Inspect Details"
                              >
                                <Eye className="w-4 h-4" />
                              </button>
                              <a
                                href={api.getInvoicePdfUrl(inv.id)}
                                target="_blank"
                                rel="noreferrer"
                                className="p-1.5 text-slate-500 hover:text-slate-800 rounded-md hover:bg-slate-100 transition inline-block"
                                title="Print / PDF View"
                              >
                                <Printer className="w-4 h-4" />
                              </a>
                              {inv.status === 'confirmed' && balance > 0 && (
                                <button
                                  onClick={() => handleOpenPayment(inv)}
                                  className="px-2.5 py-1 text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 rounded-md transition"
                                >
                                  Record Payment
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <PaginationControls
                  page={page}
                  totalPages={totalPages}
                  total={total}
                  pageSize={pageSize}
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

      {/* TAB 2: PAYMENTS LEDGER */}
      {mainTab === 'payments' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
            <div className="flex-1 min-w-[260px]">
              <input
                type="text"
                placeholder="Search by invoice #, customer name, or payment note..."
                value={paymentsSearch}
                onChange={(e) => {
                  setPaymentsSearch(e.target.value);
                  setPaymentsPage(1);
                }}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={paymentsMethodFilter}
                onChange={(e) => {
                  setPaymentsMethodFilter(e.target.value);
                  setPaymentsPage(1);
                }}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              >
                <option value="all">All Methods</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="credit_card">Credit Card</option>
                <option value="cash">Cash</option>
                <option value="other">Other</option>
              </select>

              <select
                value={paymentsReversalFilter}
                onChange={(e) => {
                  setPaymentsReversalFilter(e.target.value);
                  setPaymentsPage(1);
                }}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              >
                <option value="all">All Payments</option>
                <option value="active">Settled Only</option>
                <option value="reversed">Reversed / Refunded</option>
              </select>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            {paymentsLoading ? (
              <LoadingState message="Loading payments ledger..." rows={5} />
            ) : payments.length === 0 ? (
              <EmptyState
                title="No payments recorded"
                description="Payments recorded against invoices will appear here with full history."
              />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-sm min-w-[850px]">
                    <thead>
                      <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                        <th className="py-3 px-4">Payment Date</th>
                        <th className="py-3 px-4">Invoice #</th>
                        <th className="py-3 px-4">Customer</th>
                        <th className="py-3 px-4 text-right">Amount</th>
                        <th className="py-3 px-4">Method</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Reference Note</th>
                        <th className="py-3 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {payments.map((p) => (
                        <tr key={p.id} className="hover:bg-slate-50/60 transition">
                          <td className="py-3.5 px-4 font-mono text-slate-700">{p.payment_date}</td>
                          <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">
                            {p.invoice_number ? (
                              <button
                                onClick={() => openInvoiceDetail(p.invoice_id)}
                                className="hover:underline"
                              >
                                {p.invoice_number}
                              </button>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="py-3.5 px-4 font-medium text-slate-900">{p.customer_name || 'Customer'}</td>
                          <td className="py-3.5 px-4 text-right font-mono font-bold text-emerald-600">
                            ${Number(p.amount).toFixed(2)}
                          </td>
                          <td className="py-3.5 px-4 capitalize text-slate-600 text-xs">
                            {p.payment_method.replace('_', ' ')}
                          </td>
                          <td className="py-3.5 px-4">
                            {p.is_reversed ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800">
                                <RotateCcw className="w-3 h-3" />
                                Reversed
                              </span>
                            ) : p.reversals?.length || p.reversal ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                                <RotateCcw className="w-3 h-3" />
                                Partially refunded
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                                <CheckCircle2 className="w-3 h-3" />
                                Settled
                              </span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-xs text-slate-500 max-w-xs truncate">
                            {p.reference_note || '—'}
                            {(p.reversals || (p.reversal ? [p.reversal] : [])).map((reversal) => (
                              <span key={reversal.id} className="block text-red-600 font-medium">
                                Refund ₹${Number(reversal.reversal_amount).toFixed(2)}: {reversal.reason}
                              </span>
                            ))}
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            {!p.is_reversed ? (
                              <button
                                onClick={() => handleOpenReversal(p)}
                                className="px-2.5 py-1 text-xs font-semibold bg-red-50 text-red-700 hover:bg-red-100 border border-red-200 rounded-md transition flex items-center gap-1 ml-auto"
                              >
                                <RotateCcw className="w-3 h-3" />
                                Reverse / Refund
                              </button>
                            ) : (
                              <span className="text-xs text-slate-400 italic">Reversed</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <PaginationControls
                  page={paymentsPage}
                  totalPages={paymentsTotalPages}
                  total={paymentsTotal}
                  pageSize={paymentsPageSize}
                  onPageChange={setPaymentsPage}
                  onPageSizeChange={(sz) => {
                    setPaymentsPageSize(sz);
                    setPaymentsPage(1);
                  }}
                />
              </>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: COLLECTION QUEUE */}
      {mainTab === 'collections' && (
        <div className="space-y-5">
          {/* Aging Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="bg-red-50/80 border border-red-200 rounded-xl p-4 shadow-2xs">
              <div className="text-xs font-semibold text-red-700 uppercase tracking-wider">Total Overdue</div>
              <div className="text-xl font-bold font-mono text-red-900 mt-1">
                ${Number(collectionQueue?.total_overdue_balance || 0).toFixed(2)}
              </div>
              <div className="text-xs text-red-600 mt-0.5">
                {collectionQueue?.total_overdue_invoices || 0} overdue invoices
              </div>
            </div>

            <button
              onClick={() => setCollectionsAgingFilter(collectionsAgingFilter === '1-30' ? 'all' : '1-30')}
              className={`text-left rounded-xl p-4 border transition ${
                collectionsAgingFilter === '1-30'
                  ? 'bg-amber-100 border-amber-400 ring-2 ring-amber-500/30'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="text-xs font-semibold text-slate-500 uppercase">1–30 Days</div>
              <div className="text-lg font-bold font-mono text-slate-900 mt-1">
                ${Number(collectionQueue?.aging_breakdown?.['1-30']?.amount || 0).toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                {collectionQueue?.aging_breakdown?.['1-30']?.count || 0} items
              </div>
            </button>

            <button
              onClick={() => setCollectionsAgingFilter(collectionsAgingFilter === '31-60' ? 'all' : '31-60')}
              className={`text-left rounded-xl p-4 border transition ${
                collectionsAgingFilter === '31-60'
                  ? 'bg-amber-100 border-amber-400 ring-2 ring-amber-500/30'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="text-xs font-semibold text-slate-500 uppercase">31–60 Days</div>
              <div className="text-lg font-bold font-mono text-slate-900 mt-1">
                ${Number(collectionQueue?.aging_breakdown?.['31-60']?.amount || 0).toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                {collectionQueue?.aging_breakdown?.['31-60']?.count || 0} items
              </div>
            </button>

            <button
              onClick={() => setCollectionsAgingFilter(collectionsAgingFilter === '61-90' ? 'all' : '61-90')}
              className={`text-left rounded-xl p-4 border transition ${
                collectionsAgingFilter === '61-90'
                  ? 'bg-orange-100 border-orange-400 ring-2 ring-orange-500/30'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="text-xs font-semibold text-slate-500 uppercase">61–90 Days</div>
              <div className="text-lg font-bold font-mono text-slate-900 mt-1">
                ${Number(collectionQueue?.aging_breakdown?.['61-90']?.amount || 0).toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                {collectionQueue?.aging_breakdown?.['61-90']?.count || 0} items
              </div>
            </button>

            <button
              onClick={() => setCollectionsAgingFilter(collectionsAgingFilter === '90_plus' ? 'all' : '90_plus')}
              className={`text-left rounded-xl p-4 border transition ${
                collectionsAgingFilter === '90_plus'
                  ? 'bg-red-100 border-red-400 ring-2 ring-red-500/30'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="text-xs font-semibold text-slate-500 uppercase">90+ Days</div>
              <div className="text-lg font-bold font-mono text-red-700 mt-1">
                ${Number(collectionQueue?.aging_breakdown?.['90_plus']?.amount || 0).toFixed(2)}
              </div>
              <div className="text-xs text-red-600 mt-0.5">
                {collectionQueue?.aging_breakdown?.['90_plus']?.count || 0} items
              </div>
            </button>
          </div>

          {/* Collection Filters */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
            <div className="flex-1 min-w-[260px]">
              <input
                type="text"
                placeholder="Search collection items by customer or invoice #..."
                value={collectionsSearch}
                onChange={(e) => setCollectionsSearch(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={collectionsAgingFilter}
                onChange={(e) => setCollectionsAgingFilter(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              >
                <option value="all">All Aging Buckets</option>
                <option value="1-30">1–30 Days Overdue</option>
                <option value="31-60">31–60 Days Overdue</option>
                <option value="61-90">61–90 Days Overdue</option>
                <option value="90_plus">90+ Days Overdue</option>
              </select>

              <select
                value={collectionsSortBy}
                onChange={(e) => setCollectionsSortBy(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              >
                <option value="days_overdue">Sort by Overdue Age (Oldest)</option>
                <option value="balance">Sort by Balance Due (Highest)</option>
                <option value="due_date">Sort by Due Date</option>
              </select>
            </div>
          </div>

          {/* Queue Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            {collectionsLoading ? (
              <LoadingState message="Calculating overdue aging and collection priority..." rows={5} />
            ) : !collectionQueue || collectionQueue.items.length === 0 ? (
              <EmptyState
                title="Zero Overdue Invoices!"
                description="All issued customer invoices are either settled or within their agreed credit terms."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm min-w-[850px]">
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                      <th className="py-3 px-4">Customer</th>
                      <th className="py-3 px-4">Invoice #</th>
                      <th className="py-3 px-4 text-right">Invoice Total</th>
                      <th className="py-3 px-4 text-right">Balance Due</th>
                      <th className="py-3 px-4">Due Date</th>
                      <th className="py-3 px-4">Aging Priority</th>
                      <th className="py-3 px-4">Last Reminder</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {collectionQueue.items.map((item) => (
                      <tr key={item.invoice_id} className="hover:bg-slate-50/60 transition">
                        <td className="py-3.5 px-4 font-medium text-slate-900">
                          <div>{item.customer_name}</div>
                          {item.billing_email && (
                            <div className="text-[11px] text-slate-500 font-mono">{item.billing_email}</div>
                          )}
                        </td>
                        <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">
                          <button
                            onClick={() => openInvoiceDetail(item.invoice_id)}
                            className="hover:underline"
                          >
                            {item.invoice_number}
                          </button>
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono text-slate-600">
                          ${Number(item.total_amount).toFixed(2)}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-bold text-red-600">
                          ${Number(item.balance_due).toFixed(2)}
                        </td>
                        <td className="py-3.5 px-4 text-xs font-mono text-slate-600 whitespace-nowrap">
                          {item.due_date}
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${
                              item.days_overdue > 60
                                ? 'bg-red-100 text-red-800'
                                : item.days_overdue > 30
                                ? 'bg-orange-100 text-orange-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}
                          >
                            <AlertCircle className="w-3 h-3" />
                            {item.days_overdue} days ({item.aging_bucket})
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-500 whitespace-nowrap">
                          {item.last_reminder_sent_at ? (
                            <span className="text-emerald-700 flex items-center gap-1 font-medium">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              {new Date(item.last_reminder_sent_at).toLocaleDateString()}
                            </span>
                          ) : (
                            <span className="text-slate-400 italic">No reminder yet</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-right space-x-2 whitespace-nowrap">
                          <button
                            onClick={() => handleSendCollectionReminder(item.invoice_id, item.invoice_number)}
                            disabled={remindingInvoiceId === item.invoice_id}
                            className="px-2.5 py-1 text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 rounded-md transition disabled:opacity-50 inline-flex items-center gap-1"
                          >
                            <BellRing className="w-3 h-3" />
                            {remindingInvoiceId === item.invoice_id ? 'Sending...' : 'Remind'}
                          </button>

                          <button
                            onClick={() =>
                              handleOpenPayment({
                                id: item.invoice_id,
                                invoice_number: item.invoice_number,
                                customer_name: item.customer_name,
                                total_amount: item.total_amount,
                                paid_amount: item.paid_amount,
                                currency: item.currency,
                              })
                            }
                            className="px-2.5 py-1 text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 rounded-md transition"
                          >
                            Record Payment
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Slide-over Detail Drawer */}
      {selectedInvoice && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-2xs flex justify-end animate-in fade-in duration-200">
          <div className="w-full max-w-2xl bg-white shadow-2xl h-full flex flex-col justify-between overflow-y-auto">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-200 flex items-center justify-between sticky top-0 bg-white z-10">
              <div className="flex items-center gap-3">
                <span className="p-2 rounded-lg bg-indigo-50 text-indigo-700">
                  <FileText className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 font-mono">
                    {selectedInvoice.invoice_number}
                  </h3>
                  <div className="text-xs text-slate-500">
                    Issued {selectedInvoice.issue_date} • Due {selectedInvoice.due_date}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setSelectedInvoice(null)}
                className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="p-6 space-y-6 flex-1">
              {detailLoading && <LoadingState message="Loading document details..." rows={3} />}

              {/* Status and Action Ribbon */}
              <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200">
                <div className="space-y-1">
                  <div className="text-xs text-slate-500 font-medium">Status & Delivery</div>
                  <div className="flex items-center gap-2">
                    <span className="capitalize font-semibold text-slate-800 text-sm">
                      {selectedInvoice.status}
                    </span>
                    <span className="text-xs text-slate-400">•</span>
                    <span className="text-xs font-mono text-slate-600">
                      Send: {selectedInvoice.send_status}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {selectedInvoice.status === 'draft' && (
                    <button
                      onClick={() => handleConfirmInvoice(selectedInvoice.id)}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-2xs transition"
                    >
                      Confirm Invoice
                    </button>
                  )}
                  {selectedInvoice.status === 'confirmed' && (
                    <>
                      <button
                        onClick={() => handleSendInvoice(selectedInvoice.id)}
                        className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg flex items-center gap-1 shadow-2xs transition"
                      >
                        <Send className="w-3.5 h-3.5" />
                        Send Notice
                      </button>
                      {Number(selectedInvoice.total_amount) > Number(selectedInvoice.paid_amount) && (
                        <button
                          onClick={() => handleOpenPayment(selectedInvoice)}
                          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg flex items-center gap-1 shadow-2xs transition"
                        >
                          <CreditCard className="w-3.5 h-3.5" />
                          Record Payment
                        </button>
                      )}
                      <button
                        onClick={() => handleOpenCancelModal(selectedInvoice)}
                        className="px-3 py-1.5 border border-red-200 text-red-600 hover:bg-red-50 text-xs font-semibold rounded-lg transition"
                      >
                        Cancel
                      </button>
                    </>
                  )}
                  <a
                    href={api.getInvoicePdfUrl(selectedInvoice.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="p-1.5 border border-slate-200 text-slate-600 hover:bg-slate-100 rounded-lg transition"
                    title="Print Document"
                  >
                    <Printer className="w-4 h-4" />
                  </a>
                </div>
              </div>

              {/* Customer Snapshot */}
              <div>
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Building className="w-4 h-4 text-indigo-600" />
                  Customer Snapshot (Immutable)
                </h4>
                <div className="grid grid-cols-2 gap-3 text-xs bg-slate-50 border border-slate-200 rounded-xl p-3">
                  <div>
                    <span className="text-slate-500">Company:</span>
                    <div className="font-semibold text-slate-900">
                      {String(selectedInvoice.customer_snapshot?.company_name || selectedInvoice.customer_name || '—')}
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-500">Billing Email:</span>
                    <div className="font-mono text-slate-800">
                      {String(selectedInvoice.customer_snapshot?.billing_email || '—')}
                    </div>
                  </div>
                  <div className="col-span-2">
                    <span className="text-slate-500">Billing Address:</span>
                    <div className="text-slate-800">
                      {String(selectedInvoice.billing_address_snapshot?.address_line1 || 'Primary Account Address')}
                    </div>
                  </div>
                </div>
              </div>

              {/* Line Items Snapshot */}
              <div>
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-indigo-600" />
                  Calculated Line Items
                </h4>
                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 uppercase font-semibold">
                      <tr>
                        <th className="py-2 px-3">Item</th>
                        <th className="py-2 px-2 text-center">Qty</th>
                        <th className="py-2 px-2 text-right">Price</th>
                        <th className="py-2 px-2 text-right">Discount</th>
                        <th className="py-2 px-2 text-right">Tax</th>
                        <th className="py-2 px-3 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {selectedInvoice.lines.map((line) => (
                        <tr key={line.id}>
                          <td className="py-2.5 px-3">
                            <div className="font-medium text-slate-900">{line.description}</div>
                            {line.variant_name_snapshot && (
                              <div className="text-[11px] text-slate-500">Variant: {line.variant_name_snapshot}</div>
                            )}
                          </td>
                          <td className="py-2.5 px-2 text-center">{line.quantity}</td>
                          <td className="py-2.5 px-2 text-right font-mono">₹{Number(line.unit_price_snapshot).toFixed(2)}</td>
                          <td className="py-2.5 px-2 text-right font-mono text-emerald-600">
                            {Number(line.discount_amount) > 0 ? `-₹${Number(line.discount_amount).toFixed(2)}` : '—'}
                          </td>
                          <td className="py-2.5 px-2 text-right font-mono">
                            ${Number(line.tax_amount).toFixed(2)}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-900">
                            ${Number(line.line_total).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="p-3 bg-slate-50 border-t border-slate-200 space-y-1 text-xs">
                    <div className="flex justify-between text-slate-600">
                      <span>Subtotal:</span>
                      <span className="font-mono">₹{Number(selectedInvoice.subtotal || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-emerald-600">
                      <span>Discounts:</span>
                      <span className="font-mono">-${Number(selectedInvoice.discount_amount || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>Taxes:</span>
                      <span className="font-mono">+₹{Number(selectedInvoice.tax_amount || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm font-bold text-slate-900 pt-1 border-t border-slate-200">
                      <span>Total Invoice Amount:</span>
                      <span className="font-mono">₹{Number(selectedInvoice.total_amount).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-xs font-semibold text-emerald-700 pt-0.5">
                      <span>Total Settled (Paid):</span>
                      <span className="font-mono">₹{Number(selectedInvoice.paid_amount || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm font-bold text-red-600 pt-1 border-t border-slate-200">
                      <span>Remaining Balance Due:</span>
                      <span className="font-mono">
                        ${Math.max(0, Number(selectedInvoice.total_amount) - Number(selectedInvoice.paid_amount || 0)).toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recorded Payments & Reversals Section */}
              <div>
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <CreditCard className="w-4 h-4 text-emerald-600" />
                    Payment History & Refunds
                  </span>
                  {selectedInvoice.status === 'confirmed' &&
                    Number(selectedInvoice.total_amount) > Number(selectedInvoice.paid_amount) && (
                      <button
                        onClick={() => handleOpenPayment(selectedInvoice)}
                        className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                      >
                        + Add Payment
                      </button>
                    )}
                </h4>

                {!selectedInvoice.payments || selectedInvoice.payments.length === 0 ? (
                  <div className="text-xs text-slate-500 italic p-3 bg-slate-50 border border-slate-200 rounded-xl">
                    No payments recorded for this invoice yet.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {selectedInvoice.payments.map((pmt) => (
                      <div
                        key={pmt.id}
                        className="p-3 bg-white border border-slate-200 rounded-xl flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-bold font-mono text-emerald-700">
                              ${Number(pmt.amount).toFixed(2)}
                            </span>
                            <span className="capitalize text-slate-500">
                              via {pmt.payment_method.replace('_', ' ')}
                            </span>
                            {pmt.is_reversed ? (
                              <span className="px-1.5 py-0.5 bg-red-100 text-red-800 text-[10px] font-semibold rounded">
                                Voided / Reversed
                              </span>
                            ) : (
                              <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-semibold rounded">
                                Settled
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-400">
                            Date: {pmt.payment_date} {pmt.reference_note ? `• ${pmt.reference_note}` : ''}
                          </div>
                        </div>

                        {!pmt.is_reversed && (
                          <button
                            onClick={() =>
                              handleOpenReversal({
                                ...pmt,
                                invoice_id: selectedInvoice.id,
                                invoice_number: selectedInvoice.invoice_number,
                                customer_name: selectedInvoice.customer_name,
                                currency: selectedInvoice.currency,
                              })
                            }
                            className="px-2 py-1 text-[11px] font-semibold bg-red-50 text-red-700 hover:bg-red-100 border border-red-200 rounded transition"
                          >
                            Reverse
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Audit History Timeline */}
              {selectedInvoice.audit_history && selectedInvoice.audit_history.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <History className="w-4 h-4 text-indigo-600" />
                    Traceable Audit Trail
                  </h4>
                  <div className="space-y-2 border border-slate-200 rounded-xl p-3 bg-slate-50/50">
                    {selectedInvoice.audit_history.map((event) => (
                      <div key={event.id} className="text-xs flex items-start gap-2 bg-white p-2.5 rounded-lg border border-slate-200/60 shadow-2xs">
                        <ChevronRight className="w-3.5 h-3.5 text-indigo-500 mt-0.5 shrink-0" />
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-800">{event.action}</span>
                            <span className="text-[11px] text-slate-400">
                              {new Date(event.timestamp).toLocaleString()}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-500 mt-0.5">
                            By {event.actor_name} ({event.actor_role || 'user'})
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Accessible Payment Modal */}
      <Modal
        isOpen={paymentModalInvoice !== null}
        onClose={() => setPaymentModalInvoice(null)}
        title="Record Invoice Payment"
        subtitle={
          paymentModalInvoice
            ? `Invoice ${paymentModalInvoice.invoice_number} • ${paymentModalInvoice.customer_name}`
            : undefined
        }
      >
        {paymentModalInvoice && (
          <form onSubmit={handleRecordPaymentSubmit} className="space-y-4">
            {paymentError && (
              <AlertBanner
                type="error"
                message={paymentError}
                onClose={() => setPaymentError(null)}
              />
            )}

            <div>
              <label htmlFor="payment-amount" className="block text-xs font-semibold text-slate-700 mb-1">
                Payment Amount (₹) *
              </label>
              <input
                id="payment-amount"
                type="number"
                step="0.01"
                min="0.01"
                required
                value={paymentAmount}
                onChange={(e) => setPaymentAmount(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 font-mono font-bold"
              />
              <div className="text-[11px] text-slate-500 mt-1">
                Outstanding balance:{' '}
                <span className="font-mono font-bold text-slate-800">
                  ${Math.max(0, Number(paymentModalInvoice.total_amount) - Number(paymentModalInvoice.paid_amount)).toFixed(2)}
                </span>
              </div>
            </div>

            <div>
              <label htmlFor="payment-method" className="block text-xs font-semibold text-slate-700 mb-1">
                Payment Method *
              </label>
              <select
                id="payment-method"
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              >
                <option value="bank_transfer">Bank Transfer (ACH / Wire)</option>
                <option value="credit_card">Credit Card</option>
                <option value="cash">Cash / Cheque</option>
                <option value="other">Other Manual Settlement</option>
              </select>
            </div>

            <div>
              <label htmlFor="payment-note" className="block text-xs font-semibold text-slate-700 mb-1">
                Reference Note / Transaction ID
              </label>
              <input
                id="payment-note"
                type="text"
                value={paymentNote}
                onChange={(e) => setPaymentNote(e.target.value)}
                placeholder="e.g. Wire reference #94829"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setPaymentModalInvoice(null)}
                className="px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={paymentSubmitting}
                className="px-4 py-2 text-xs sm:text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 transition"
              >
                {paymentSubmitting ? 'Recording...' : 'Save Payment'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Payment Reversal / Refund Modal */}
      <Modal
        isOpen={reversalModalPayment !== null}
        onClose={() => setReversalModalPayment(null)}
        title="Reverse / Refund Payment"
        subtitle={
          reversalModalPayment
            ? `Payment of ₹${Number(reversalModalPayment.amount).toFixed(2)} on invoice ${reversalModalPayment.invoice_number || ''}`
            : undefined
        }
      >
        {reversalModalPayment && (
          <form onSubmit={handleReversalSubmit} className="space-y-4">
            {reversalError && (
              <AlertBanner
                type="error"
                message={reversalError}
                onClose={() => setReversalError(null)}
              />
            )}

            <p className="text-xs text-slate-600">
              This action adds an immutable refund record and restores that amount to the invoice balance. You can record multiple partial refunds until the payment is fully reversed.
            </p>

            <div>
              <label htmlFor="reversal-amount" className="block text-xs font-semibold text-slate-700 mb-1">
                Reversal Amount (₹) *
              </label>
              <input
                id="reversal-amount"
                type="number"
                step="0.01"
                min="0.01"
                max={Math.max(0, Number(reversalModalPayment.amount) - (reversalModalPayment.reversals || (reversalModalPayment.reversal ? [reversalModalPayment.reversal] : [])).reduce((sum, item) => sum + Number(item.reversal_amount), 0))}
                required
                value={reversalAmount}
                onChange={(e) => setReversalAmount(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500/20 focus:border-red-500 font-mono font-bold"
              />
            </div>

            <div>
              <label htmlFor="reversal-reason" className="block text-xs font-semibold text-slate-700 mb-1">
                Reversal / Refund Audit Reason *
              </label>
              <textarea
                id="reversal-reason"
                required
                rows={3}
                value={reversalReason}
                onChange={(e) => setReversalReason(e.target.value)}
                placeholder="e.g. Bank chargeback, payment entered in error, customer credit request..."
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setReversalModalPayment(null)}
                className="px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition"
              >
                Keep Payment
              </button>
              <button
                type="submit"
                disabled={reversalSubmitting || !reversalReason.trim()}
                className="px-4 py-2 text-xs sm:text-sm font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50 transition"
              >
                {reversalSubmitting ? 'Processing Reversal...' : 'Confirm Reversal'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Cancel Invoice Modal */}
      <Modal
        isOpen={cancelModalInvoice !== null}
        onClose={() => setCancelModalInvoice(null)}
        title="Cancel Invoice"
        subtitle={cancelModalInvoice ? `Invoice ${cancelModalInvoice.invoice_number}` : undefined}
      >
        {cancelModalInvoice && (
          <form onSubmit={handleCancelSubmit} className="space-y-4">
            {cancelError && (
              <AlertBanner
                type="error"
                message={cancelError}
                onClose={() => setCancelError(null)}
              />
            )}
            <p className="text-xs text-slate-600">
              Cancelling an invoice marks it permanently void. Please provide an audit reason for financial compliance.
            </p>
            <div>
              <label htmlFor="cancel-reason" className="block text-xs font-semibold text-slate-700 mb-1">
                Cancellation Reason *
              </label>
              <textarea
                id="cancel-reason"
                required
                rows={3}
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="e.g. Customer requested upgrade to annual billing plan..."
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setCancelModalInvoice(null)}
                className="px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition"
              >
                Keep Invoice
              </button>
              <button
                type="submit"
                disabled={cancelSubmitting || !cancelReason.trim()}
                className="px-4 py-2 text-xs sm:text-sm font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50 transition"
              >
                {cancelSubmitting ? 'Cancelling...' : 'Confirm Cancellation'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Generate Draft Invoice Modal */}
      <Modal
        isOpen={showGenerateModal}
        onClose={() => setShowGenerateModal(false)}
        title="Generate Invoice from Subscription"
        subtitle="Create an invoice draft or committed demand copying customer, lines, taxes, and discounts."
      >
        <form onSubmit={handleGenerateInvoiceSubmit} className="space-y-4">
          {generateError && (
            <AlertBanner
              type="error"
              message={generateError}
              onClose={() => setGenerateError(null)}
            />
          )}

          <div>
            <label htmlFor="select-sub" className="block text-xs font-semibold text-slate-700 mb-1">
              Select Active Subscription *
            </label>
            <select
              id="select-sub"
              required
              value={selectedSubId}
              onChange={(e) => setSelectedSubId(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 font-mono"
            >
              {activeSubscriptions.length === 0 ? (
                <option value="">No active subscriptions found</option>
              ) : (
                activeSubscriptions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.subscription_number} — {s.customer_name} ({s.plan_name})
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="period-start" className="block text-xs font-semibold text-slate-700 mb-1">
                Period Start (Optional)
              </label>
              <input
                id="period-start"
                type="date"
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
            <div>
              <label htmlFor="period-end" className="block text-xs font-semibold text-slate-700 mb-1">
                Period End (Optional)
              </label>
              <input
                id="period-end"
                type="date"
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="create-as-draft"
              checked={createAsDraft}
              onChange={(e) => setCreateAsDraft(e.target.checked)}
              className="rounded text-indigo-600 focus:ring-indigo-500 h-4 w-4"
            />
            <label htmlFor="create-as-draft" className="text-xs text-slate-700 select-none">
              Save as <span className="font-semibold">Draft</span> for review before issuing
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setShowGenerateModal(false)}
              className="px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={generatingDraft || !selectedSubId}
              className="px-4 py-2 text-xs sm:text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 transition"
            >
              {generatingDraft ? 'Generating...' : 'Create Invoice'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

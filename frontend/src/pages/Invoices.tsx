import React, { useEffect, useState, useCallback } from 'react';
import { api, InvoiceApiItem, InvoiceDetailApiItem, SubscriptionApiItem } from '../services/api';
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
  Ban,
  Layers,
  History,
  X,
  ChevronRight,
} from 'lucide-react';

const STATUS_OPTIONS: FilterOption[] = [
  { label: 'Confirmed (Open)', value: 'confirmed' },
  { label: 'Paid', value: 'paid' },
  { label: 'Overdue', value: 'overdue' },
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

export const Invoices: React.FC<InvoicesProps> = ({ onNavigate }) => {
  const [invoices, setInvoices] = useState<InvoiceApiItem[]>([]);
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
  const [sortValue, setSortValue] = useState<string>('issue_date-desc');

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

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

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

  const handleOpenPayment = (inv: InvoiceApiItem) => {
    const balance = Number(inv.total_amount) - Number(inv.paid_amount);
    setPaymentModalInvoice(inv);
    setPaymentAmount(balance > 0 ? balance.toFixed(2) : '0.00');
    setPaymentMethod('bank_transfer');
    setPaymentNote('Remittance recorded via staff dashboard');
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
        message: `Payment of $${amountNum.toFixed(2)} recorded successfully against invoice ${paymentModalInvoice.invoice_number}.`,
      });
      setPaymentModalInvoice(null);
      if (selectedInvoice && selectedInvoice.id === paymentModalInvoice.id) {
        await openInvoiceDetail(selectedInvoice.id);
      }
      await fetchInvoices();
    } catch (err) {
      setPaymentError(err instanceof Error ? err.message : 'Failed to record payment.');
    } finally {
      setPaymentSubmitting(false);
    }
  };

  const handleConfirmInvoice = async (invId: string, invoiceNumber: string) => {
    try {
      await api.confirmInvoice(invId);
      setFeedback({ type: 'success', message: `Invoice ${invoiceNumber} confirmed successfully.` });
      if (selectedInvoice && selectedInvoice.id === invId) {
        await openInvoiceDetail(invId);
      }
      await fetchInvoices();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to confirm invoice.' });
    }
  };

  const handleSendInvoice = async (invId: string, invoiceNumber: string) => {
    try {
      await api.sendInvoice(invId);
      setFeedback({ type: 'success', message: `Invoice ${invoiceNumber} sent to customer billing email.` });
      if (selectedInvoice && selectedInvoice.id === invId) {
        await openInvoiceDetail(invId);
      }
      await fetchInvoices();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to send invoice.' });
    }
  };

  const handleOpenCancel = (inv: InvoiceApiItem) => {
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
      setFeedback({ type: 'success', message: `Invoice ${cancelModalInvoice.invoice_number} has been cancelled.` });
      setCancelModalInvoice(null);
      if (selectedInvoice && selectedInvoice.id === cancelModalInvoice.id) {
        await openInvoiceDetail(selectedInvoice.id);
      }
      await fetchInvoices();
    } catch (err) {
      setCancelError(err instanceof Error ? err.message : 'Failed to cancel invoice.');
    } finally {
      setCancelSubmitting(false);
    }
  };

  const handleOpenGenerateModal = async () => {
    setShowGenerateModal(true);
    setSelectedSubId('');
    setPeriodStart('');
    setPeriodEnd('');
    setCreateAsDraft(true);
    setGenerateError(null);

    try {
      const subs = await api.getSubscriptions({ status: 'active', pageSize: 100 });
      setActiveSubscriptions(subs.items);
      if (subs.items.length > 0) {
        setSelectedSubId(subs.items[0].id);
      }
    } catch {
      setActiveSubscriptions([]);
    }
  };

  const handleGenerateInvoiceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSubId) return;

    setGeneratingDraft(true);
    setGenerateError(null);
    try {
      const created = await api.generateDraftInvoice({
        subscription_id: selectedSubId,
        billing_period_start: periodStart || undefined,
        billing_period_end: periodEnd || undefined,
        as_draft: createAsDraft,
      });
      setFeedback({
        type: 'success',
        message: `Invoice ${created.invoice_number} created in ${created.status.toUpperCase()} status.`,
      });
      setShowGenerateModal(false);
      await fetchInvoices();
      await openInvoiceDetail(created.id);
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

  const getStatusBadge = (status: string, isOverdue: boolean) => {
    if (isOverdue && status !== 'paid' && status !== 'cancelled') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800">
          <AlertTriangle className="w-3 h-3" />
          Overdue
        </span>
      );
    }
    switch (status) {
      case 'paid':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
            <CheckCircle2 className="w-3 h-3" />
            Paid
          </span>
        );
      case 'confirmed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
            <Clock className="w-3 h-3" />
            Open
          </span>
        );
      case 'draft':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
            Draft
          </span>
        );
      case 'cancelled':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-700">
            <XCircle className="w-3 h-3" />
            Canceled
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
        title="Invoices & Collections"
        subtitle="Manage billing documents, immutable line snapshots, payment tracking, and print exports."
        breadcrumbs={[
          { label: 'Brightloop', tabKey: 'dashboard' },
          { label: 'Operations', tabKey: 'dashboard' },
          { label: 'Invoices & Payments' },
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
              onClick={handleOpenGenerateModal}
              className="px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 flex items-center gap-1.5 shadow-xs transition"
            >
              <Plus className="w-4 h-4" />
              Generate Draft Invoice
            </button>
            <button
              onClick={fetchInvoices}
              className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
              title="Refresh"
              aria-label="Refresh invoices"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
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
                          {inv.billing_period_start} &rarr; {inv.billing_period_end}
                        </td>
                        <td className="py-3.5 px-4">{getStatusBadge(inv.status, inv.is_overdue)}</td>
                        <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">
                          ${Number(inv.total_amount).toFixed(2)}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono text-emerald-700 font-medium">
                          ${Number(inv.paid_amount).toFixed(2)}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900">
                          ${balance > 0 ? balance.toFixed(2) : '0.00'}
                        </td>
                        <td className="py-3.5 px-4 text-xs font-medium text-slate-600 whitespace-nowrap">
                          {inv.due_date}
                        </td>
                        <td className="py-3.5 px-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => openInvoiceDetail(inv.id)}
                              className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-md transition"
                              title="View details"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                            <a
                              href={api.getInvoicePdfUrl(inv.id)}
                              target="_blank"
                              rel="noreferrer"
                              className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-md transition"
                              title="Print / View PDF"
                            >
                              <Printer className="w-4 h-4" />
                            </a>
                            {inv.status === 'draft' && (
                              <button
                                onClick={() => handleConfirmInvoice(inv.id, inv.invoice_number)}
                                className="px-2 py-1 text-xs font-semibold rounded bg-blue-50 text-blue-700 hover:bg-blue-100 transition"
                              >
                                Confirm
                              </button>
                            )}
                            {inv.status !== 'paid' && inv.status !== 'cancelled' && balance > 0 && (
                              <button
                                onClick={() => handleOpenPayment(inv)}
                                className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold rounded bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition"
                              >
                                <CreditCard className="w-3.5 h-3.5" />
                                Pay
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

      {/* Invoice Detail Drawer */}
      {selectedInvoice && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/50 backdrop-blur-xs flex justify-end">
          <div className="bg-white w-full max-w-2xl h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-base font-bold text-slate-900">
                    {selectedInvoice.invoice_number}
                  </span>
                  {getStatusBadge(selectedInvoice.status, selectedInvoice.is_overdue)}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  Customer: <span className="font-semibold text-slate-700">{selectedInvoice.customer_name}</span>
                </div>
              </div>
              <button
                onClick={() => setSelectedInvoice(null)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200/50 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {detailLoading && <LoadingState message="Loading invoice detail..." />}

              {/* Action Bar */}
              <div className="flex flex-wrap items-center gap-2 p-3 bg-slate-100/70 rounded-xl border border-slate-200 text-xs">
                <a
                  href={api.getInvoicePdfUrl(selectedInvoice.id)}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium flex items-center gap-1.5 shadow-2xs"
                >
                  <Printer className="w-3.5 h-3.5 text-slate-500" />
                  Print / PDF View
                </a>
                {selectedInvoice.status === 'draft' && (
                  <button
                    onClick={() => handleConfirmInvoice(selectedInvoice.id, selectedInvoice.invoice_number)}
                    className="px-3 py-1.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 flex items-center gap-1.5 shadow-2xs"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Confirm Invoice
                  </button>
                )}
                {selectedInvoice.status !== 'cancelled' && (
                  <button
                    onClick={() => handleSendInvoice(selectedInvoice.id, selectedInvoice.invoice_number)}
                    className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium flex items-center gap-1.5 shadow-2xs"
                  >
                    <Send className="w-3.5 h-3.5 text-indigo-600" />
                    {selectedInvoice.send_status === 'sent' ? 'Resend Notice' : 'Send to Customer'}
                  </button>
                )}
                {selectedInvoice.status !== 'paid' && selectedInvoice.status !== 'cancelled' && (
                  <button
                    onClick={() => handleOpenPayment(selectedInvoice)}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 flex items-center gap-1.5 shadow-2xs"
                  >
                    <CreditCard className="w-3.5 h-3.5" />
                    Record Payment
                  </button>
                )}
                {selectedInvoice.status !== 'cancelled' && Number(selectedInvoice.paid_amount) === 0 && (
                  <button
                    onClick={() => handleOpenCancel(selectedInvoice)}
                    className="px-3 py-1.5 rounded-lg bg-white border border-red-200 text-red-600 hover:bg-red-50 font-medium flex items-center gap-1.5 shadow-2xs"
                  >
                    <Ban className="w-3.5 h-3.5" />
                    Cancel Invoice
                  </button>
                )}
              </div>

              {/* Cancellation Banner */}
              {selectedInvoice.cancellation_reason && (
                <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800">
                  <div className="font-semibold flex items-center gap-1.5">
                    <XCircle className="w-4 h-4 text-red-600" />
                    Cancelled Reason
                  </div>
                  <div className="mt-1 text-slate-700">{selectedInvoice.cancellation_reason}</div>
                </div>
              )}

              {/* Dates & Financials Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase">Billing Period</div>
                  <div className="text-xs font-semibold text-slate-900 mt-1">
                    {selectedInvoice.billing_period_start} &rarr; {selectedInvoice.billing_period_end}
                  </div>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase">Due Date</div>
                  <div className="text-xs font-semibold text-slate-900 mt-1">{selectedInvoice.due_date}</div>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase">Total Amount</div>
                  <div className="text-sm font-bold text-slate-900 mt-1">
                    ${Number(selectedInvoice.total_amount).toFixed(2)}
                  </div>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase">Balance Due</div>
                  <div className="text-sm font-bold text-red-600 mt-1">
                    ${Number(selectedInvoice.outstanding_balance || 0).toFixed(2)}
                  </div>
                </div>
              </div>

              {/* Line Items Snapshot */}
              <div>
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-indigo-600" />
                  Immutable Issued Lines
                </h4>
                <div className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase">
                      <tr>
                        <th className="py-2.5 px-3">Description</th>
                        <th className="py-2.5 px-2 text-center">Qty</th>
                        <th className="py-2.5 px-2 text-right">Price</th>
                        <th className="py-2.5 px-2 text-right">Discount</th>
                        <th className="py-2.5 px-2 text-right">Tax</th>
                        <th className="py-2.5 px-3 text-right">Total</th>
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
                          <td className="py-2.5 px-2 text-right font-mono">${Number(line.unit_price_snapshot).toFixed(2)}</td>
                          <td className="py-2.5 px-2 text-right font-mono text-emerald-600">
                            {Number(line.discount_amount) > 0 ? `-$${Number(line.discount_amount).toFixed(2)}` : '—'}
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
                      <span className="font-mono">${Number(selectedInvoice.subtotal || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-emerald-600">
                      <span>Discounts:</span>
                      <span className="font-mono">-${Number(selectedInvoice.discount_amount || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>Taxes:</span>
                      <span className="font-mono">+${Number(selectedInvoice.tax_amount || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm font-bold text-slate-900 pt-1 border-t border-slate-200">
                      <span>Total Invoice Amount:</span>
                      <span className="font-mono">${Number(selectedInvoice.total_amount).toFixed(2)}</span>
                    </div>
                  </div>
                </div>
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
                Payment Amount ($)
              </label>
              <input
                id="payment-amount"
                type="number"
                step="0.01"
                min="0.01"
                value={paymentAmount}
                onChange={(e) => setPaymentAmount(e.target.value)}
                required
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
              <span className="text-xs text-slate-500 mt-1 block">
                Total: ${Number(paymentModalInvoice.total_amount).toFixed(2)} | Paid:{' '}
                ${Number(paymentModalInvoice.paid_amount).toFixed(2)}
              </span>
            </div>

            <div>
              <label htmlFor="payment-method" className="block text-xs font-semibold text-slate-700 mb-1">
                Payment Method
              </label>
              <select
                id="payment-method"
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              >
                <option value="bank_transfer">Bank Transfer (ACH / Wire)</option>
                <option value="credit_card">Credit Card</option>
                <option value="manual_check">Check / Cheque</option>
                <option value="portal">Customer Portal</option>
              </select>
            </div>

            <div>
              <label htmlFor="payment-note" className="block text-xs font-semibold text-slate-700 mb-1">
                Reference / Note (Optional)
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

          <div className="flex items-center gap-2 pt-2">
            <input
              id="create-as-draft"
              type="checkbox"
              checked={createAsDraft}
              onChange={(e) => setCreateAsDraft(e.target.checked)}
              className="rounded text-indigo-600 focus:ring-indigo-500"
            />
            <label htmlFor="create-as-draft" className="text-xs font-medium text-slate-700">
              Create as editable Draft (recommended for review before confirming)
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
              {generatingDraft ? 'Generating...' : 'Generate Invoice'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

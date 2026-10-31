import React, { useEffect, useState, useCallback } from 'react';
import { api, InvoiceApiItem } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { SearchAndFilterBar, FilterOption, SortOption } from '../components/common/SearchAndFilterBar';
import { PaginationControls } from '../components/common/PaginationControls';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { AlertBanner } from '../components/common/AlertBanner';
import { Modal } from '../components/common/Modal';
import { CheckCircle2, Clock, AlertTriangle, CreditCard, RefreshCw, XCircle } from 'lucide-react';

const STATUS_OPTIONS: FilterOption[] = [
  { label: 'Confirmed (Open)', value: 'confirmed' },
  { label: 'Paid', value: 'paid' },
  { label: 'Overdue', value: 'overdue' },
  { label: 'Draft', value: 'draft' },
  { label: 'Canceled', value: 'canceled' },
];

const SORT_OPTIONS: SortOption[] = [
  { label: 'Issue Date (Newest)', sortBy: 'issue_date', sortOrder: 'desc' },
  { label: 'Issue Date (Oldest)', sortBy: 'issue_date', sortOrder: 'asc' },
  { label: 'Due Date (Earliest)', sortBy: 'due_date', sortOrder: 'asc' },
  { label: 'Total Amount (High to Low)', sortBy: 'total_amount', sortOrder: 'desc' },
  { label: 'Outstanding Balance', sortBy: 'outstanding_balance', sortOrder: 'desc' },
];

export const Invoices: React.FC = () => {
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

  // Payment Modal State
  const [paymentModalInvoice, setPaymentModalInvoice] = useState<InvoiceApiItem | null>(null);
  const [paymentAmount, setPaymentAmount] = useState<string>('');
  const [paymentMethod, setPaymentMethod] = useState<string>('bank_transfer');
  const [paymentNote, setPaymentNote] = useState<string>('');
  const [paymentSubmitting, setPaymentSubmitting] = useState<boolean>(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);

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
      await fetchInvoices();
    } catch (err) {
      setPaymentError(err instanceof Error ? err.message : 'Failed to record payment.');
    } finally {
      setPaymentSubmitting(false);
    }
  };

  const handleResetFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setSortValue('issue_date-desc');
    setPage(1);
  };

  const getStatusBadge = (status: string, isOverdue: boolean) => {
    if (isOverdue && status !== 'paid' && status !== 'canceled') {
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
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800">
            Draft
          </span>
        );
      case 'canceled':
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
        subtitle="Track billing documents, payment allocations, outstanding balances, and aging collections."
        breadcrumbs={[
          { label: 'Brightloop' },
          { label: 'Operations' },
          { label: 'Invoices & Payments' },
        ]}
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
          <button
            onClick={fetchInvoices}
            className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
            title="Refresh"
            aria-label="Refresh invoices"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
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
              <table className="w-full text-left border-collapse text-sm min-w-[750px]">
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
                          {inv.invoice_number}
                        </td>
                        <td className="py-3.5 px-4 font-medium text-slate-900">{inv.customer_name}</td>
                        <td className="py-3.5 px-4 text-xs text-slate-500 whitespace-nowrap">
                          {inv.billing_period_start} → {inv.billing_period_end}
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
                        <td className="py-3.5 px-4 text-right">
                          {inv.status !== 'paid' && inv.status !== 'canceled' && balance > 0 && (
                            <button
                              onClick={() => handleOpenPayment(inv)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-md bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition"
                            >
                              <CreditCard className="w-3.5 h-3.5" />
                              Pay
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
                Outstanding Balance: $
                {(
                  Number(paymentModalInvoice.total_amount) -
                  Number(paymentModalInvoice.paid_amount)
                ).toFixed(2)}
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
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              >
                <option value="bank_transfer">Bank Transfer / ACH</option>
                <option value="credit_card">Credit Card</option>
                <option value="direct_debit">Direct Debit</option>
                <option value="cheque">Cheque</option>
                <option value="other">Other Manual Remittance</option>
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
                placeholder="e.g. Wire ref #84920"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setPaymentModalInvoice(null)}
                className="px-4 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={paymentSubmitting}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700 transition disabled:opacity-50"
              >
                {paymentSubmitting ? 'Recording...' : 'Confirm Payment'}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
};

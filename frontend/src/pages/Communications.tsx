import React, { useCallback, useEffect, useState } from 'react';
import { api, InvoiceApiItem, OutboxMessageItem, SubscriptionApiItem } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { PaginationControls } from '../components/common/PaginationControls';
import { AlertBanner } from '../components/common/AlertBanner';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingState } from '../components/common/LoadingState';
import { Mail, RefreshCw, RotateCcw, Send } from 'lucide-react';

interface CommunicationsProps {
  onNavigate?: (tabKey: string) => void;
}

export const Communications: React.FC<CommunicationsProps> = ({ onNavigate }) => {
  const [quotations, setQuotations] = useState<SubscriptionApiItem[]>([]);
  const [invoices, setInvoices] = useState<InvoiceApiItem[]>([]);
  const [messages, setMessages] = useState<OutboxMessageItem[]>([]);
  const [outboxPage, setOutboxPage] = useState(1);
  const [outboxTotal, setOutboxTotal] = useState(0);
  const [outboxTotalPages, setOutboxTotalPages] = useState(1);
  const [quotationId, setQuotationId] = useState('');
  const [invoiceId, setInvoiceId] = useState('');
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [subscriptionPage, invoicePage, outboxResult] = await Promise.all([
        api.getSubscriptions({ page: 1, pageSize: 100 }),
        api.getInvoices({ page: 1, pageSize: 100 }),
        api.getCommunicationsOutbox({ page: outboxPage, pageSize: 10, status: 'FAILED' }),
      ]);
      const pendingQuotes = subscriptionPage.items.filter((item) => item.status === 'quotation');
      const sendableInvoices = invoicePage.items.filter((item) => item.status === 'confirmed' || item.status === 'paid');
      setQuotations(pendingQuotes);
      setInvoices(sendableInvoices);
      setMessages(outboxResult.items);
      setOutboxTotal(outboxResult.total);
      setOutboxTotalPages(outboxResult.totalPages);
      setQuotationId((current) => pendingQuotes.some((item) => item.id === current) ? current : pendingQuotes[0]?.id || '');
      setInvoiceId((current) => sendableInvoices.some((item) => item.id === current) ? current : sendableInvoices[0]?.id || '');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load email communications.');
    } finally {
      setLoading(false);
    }
  }, [outboxPage]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const sendQuotation = async () => {
    if (!quotationId) return;
    setBusyAction('quotation');
    setFeedback(null);
    try {
      const result = await api.sendQuotationEmail(quotationId);
      setFeedback({ type: 'success', message: result.message });
      await refresh();
    } catch (reason) {
      setFeedback({ type: 'error', message: reason instanceof Error ? reason.message : 'Could not queue the quotation email.' });
    } finally {
      setBusyAction(null);
    }
  };

  const sendInvoice = async () => {
    if (!invoiceId) return;
    setBusyAction('invoice');
    setFeedback(null);
    try {
      const result = await api.sendInvoiceEmail(invoiceId);
      setFeedback({ type: 'success', message: result.message });
      await refresh();
    } catch (reason) {
      setFeedback({ type: 'error', message: reason instanceof Error ? reason.message : 'Could not queue the invoice email.' });
    } finally {
      setBusyAction(null);
    }
  };

  const retryMessage = async (message: OutboxMessageItem) => {
    setBusyAction(message.id);
    setFeedback(null);
    try {
      await api.retryCommunicationEmail(message.id);
      setFeedback({ type: 'success', message: 'Email queued for another delivery attempt.' });
      await refresh();
    } catch (reason) {
      setFeedback({ type: 'error', message: reason instanceof Error ? reason.message : 'Could not retry email delivery.' });
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Communications"
        subtitle="Send quotations and invoices, then review and retry email deliveries that need attention."
        breadcrumbs={[{ label: 'Brightloop', tabKey: 'dashboard' }, { label: 'Operations', tabKey: 'dashboard' }, { label: 'Communications' }]}
        onSelectTab={onNavigate}
        actions={
          <button onClick={() => void refresh()} disabled={loading} className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition disabled:opacity-50" title="Refresh" aria-label="Refresh communications">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        }
      />

      {feedback && <AlertBanner type={feedback.type} message={feedback.message} onClose={() => setFeedback(null)} />}
      {error && <AlertBanner type="error" message={error} onClose={() => setError(null)} />}

      <section className="grid gap-4 lg:grid-cols-2" aria-label="Send email">
        <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
          <div className="flex items-center gap-3">
            <span className="h-10 w-10 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center"><Mail className="w-5 h-5" /></span>
            <div><h2 className="font-semibold text-slate-900">Send a quotation</h2><p className="text-sm text-slate-500">Email a current offer to its customer.</p></div>
          </div>
          <label className="block text-sm font-medium text-slate-700" htmlFor="quote-to-send">Quotation</label>
          <select id="quote-to-send" value={quotationId} onChange={(event) => setQuotationId(event.target.value)} disabled={loading || quotations.length === 0} className="w-full border border-slate-300 rounded-lg px-3 py-2.5 bg-white text-sm">
            {quotations.length === 0 ? <option value="">No open quotations available</option> : quotations.map((quote) => <option key={quote.id} value={quote.id}>{quote.subscription_number} · {quote.customer_name} · {quote.plan_name}</option>)}
          </select>
          <button onClick={() => void sendQuotation()} disabled={!quotationId || busyAction !== null} className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50">
            <Send className="w-4 h-4" />{busyAction === 'quotation' ? 'Queueing…' : 'Queue quotation email'}
          </button>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
          <div className="flex items-center gap-3">
            <span className="h-10 w-10 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center"><Mail className="w-5 h-5" /></span>
            <div><h2 className="font-semibold text-slate-900">Send an invoice</h2><p className="text-sm text-slate-500">Send a confirmed or paid invoice to its billing contact.</p></div>
          </div>
          <label className="block text-sm font-medium text-slate-700" htmlFor="invoice-to-send">Invoice</label>
          <select id="invoice-to-send" value={invoiceId} onChange={(event) => setInvoiceId(event.target.value)} disabled={loading || invoices.length === 0} className="w-full border border-slate-300 rounded-lg px-3 py-2.5 bg-white text-sm">
            {invoices.length === 0 ? <option value="">No sendable invoices available</option> : invoices.map((invoice) => <option key={invoice.id} value={invoice.id}>{invoice.invoice_number} · {invoice.customer_name} · {invoice.total_amount}</option>)}
          </select>
          <button onClick={() => void sendInvoice()} disabled={!invoiceId || busyAction !== null} className="inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50">
            <Send className="w-4 h-4" />{busyAction === 'invoice' ? 'Queueing…' : 'Queue invoice email'}
          </button>
        </div>
      </section>

      <section className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3">
          <div><h2 className="font-semibold text-slate-900">Failed email deliveries</h2><p className="text-sm text-slate-500">Delivery errors stay visible here until an operator retries them.</p></div>
          <span className="rounded-full bg-rose-50 text-rose-700 px-2.5 py-1 text-xs font-semibold">{outboxTotal} failed</span>
        </div>
        {loading ? <LoadingState message="Loading email delivery history…" rows={4} /> : messages.length === 0 ? (
          <div className="p-6"><EmptyState title="No failed emails" description="All queued emails have either been delivered or are still in progress." /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm min-w-[900px]">
              <thead><tr className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider"><th className="px-5 py-3">Email</th><th className="px-5 py-3">Attempts</th><th className="px-5 py-3">Last error</th><th className="px-5 py-3">Created</th><th className="px-5 py-3 text-right">Action</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {messages.map((message) => (
                  <tr key={message.id} className="align-top">
                    <td className="px-5 py-4">
                      <div className="font-medium text-slate-900">{message.subject || message.message_type?.replace(/_/g, ' ') || 'Notification'}</div>
                      <div className="mt-1 text-xs text-slate-500">To: {message.recipient || 'Recipient not available'}</div>
                      <div className="mt-1 font-mono text-[10px] text-slate-400">{message.id}</div>
                    </td>
                    <td className="px-5 py-4 text-slate-700">{message.retry_count} / {message.max_retries}</td>
                    <td className="px-5 py-4 text-rose-700 max-w-lg break-words">{message.last_error || 'No error details recorded.'}</td>
                    <td className="px-5 py-4 text-slate-600 whitespace-nowrap">{new Date(message.created_at).toLocaleString()}</td>
                    <td className="px-5 py-4 text-right"><button onClick={() => void retryMessage(message)} disabled={busyAction !== null} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-indigo-200 bg-indigo-50 text-indigo-700 text-xs font-semibold hover:bg-indigo-100 disabled:opacity-50"><RotateCcw className="w-3.5 h-3.5" />{busyAction === message.id ? 'Queueing…' : 'Retry'}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <PaginationControls
              page={outboxPage}
              pageSize={10}
              total={outboxTotal}
              totalPages={outboxTotalPages}
              onPageChange={setOutboxPage}
              onPageSizeChange={() => setOutboxPage(1)}
              pageSizeOptions={[10]}
            />
          </div>
        )}
      </section>
    </div>
  );
};

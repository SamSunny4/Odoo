import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { CheckCircle2, Clock, AlertTriangle, CreditCard, Printer, RefreshCw } from 'lucide-react';

interface InvoiceItem {
  id: string;
  invoice_number: string;
  customer_name: string;
  billing_period_start: string;
  billing_period_end: string;
  total_amount: number;
  paid_amount: number;
  due_date: string;
  status: string;
  is_overdue: boolean;
}

export const Invoices: React.FC = () => {
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isLive, setIsLive] = useState<boolean>(false);

  const fetchInvoices = async () => {
    setLoading(true);
    try {
      const data = await api.getInvoices();
      setInvoices(data);
      setIsLive(true);
    } catch {
      setInvoices([
        {
          id: '1',
          invoice_number: 'INV-2026-0001',
          customer_name: 'Acme Corporation',
          billing_period_start: '2026-10-01',
          billing_period_end: '2026-10-31',
          total_amount: 995.50,
          paid_amount: 995.50,
          due_date: '2026-10-15',
          status: 'paid',
          is_overdue: false,
        },
      ]);
      setIsLive(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, []);

  const handlePay = async (invoiceId: string, balance: number) => {
    const amountStr = prompt(`Enter payment amount to record (Balance: $${balance.toFixed(2)}):`, balance.toFixed(2));
    if (!amountStr) return;
    const amount = parseFloat(amountStr);
    if (isNaN(amount) || amount <= 0) {
      alert('Invalid payment amount');
      return;
    }

    try {
      await api.recordPayment({
        invoice_id: invoiceId,
        amount,
        payment_method: 'bank_transfer',
        payment_date: new Date().toISOString().split('T')[0],
        reference_note: 'Customer remittance via portal/bank',
      });
      alert('Payment recorded successfully.');
      await fetchInvoices();
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Invoices & Collections</h1>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                isLive ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {isLive ? '● Live API Data' : 'Cached Baseline'}
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Immutable invoice snapshots with automatic overdue derivation and append-only payment recording.
          </p>
        </div>
        <button
          onClick={fetchInvoices}
          className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 transition self-start sm:self-auto"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
              <th className="py-3 px-4">Invoice #</th>
              <th className="py-3 px-4">Customer</th>
              <th className="py-3 px-4">Billing Period</th>
              <th className="py-3 px-4 text-right">Total</th>
              <th className="py-3 px-4 text-right">Paid Balance</th>
              <th className="py-3 px-4">Due Date</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {invoices.map((inv) => {
              const total = Number(inv.total_amount);
              const paid = Number(inv.paid_amount);
              const balance = Math.max(0, total - paid);

              return (
                <tr key={inv.id} className="hover:bg-slate-50/60 transition">
                  <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">{inv.invoice_number}</td>
                  <td className="py-3.5 px-4 font-medium text-slate-900">{inv.customer_name}</td>
                  <td className="py-3.5 px-4 text-xs text-slate-500">
                    {inv.billing_period_start} – {inv.billing_period_end}
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">
                    ${total.toFixed(2)}
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono">
                    <span className={paid >= total ? 'text-emerald-700 font-semibold' : 'text-slate-700'}>
                      ${paid.toFixed(2)}
                    </span>
                    {balance > 0 && (
                      <div className="text-[11px] text-amber-600 font-medium">Due: ${balance.toFixed(2)}</div>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-xs font-medium text-slate-600">{inv.due_date}</td>
                  <td className="py-3.5 px-4">
                    {inv.status === 'paid' ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                        <CheckCircle2 className="w-3 h-3" />
                        Paid
                      </span>
                    ) : inv.is_overdue ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 animate-pulse">
                        <AlertTriangle className="w-3 h-3" />
                        Overdue
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
                        <Clock className="w-3 h-3" />
                        Open
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button title="Print / View" className="p-1 text-slate-400 hover:text-slate-700 transition">
                        <Printer className="w-4 h-4" />
                      </button>
                      {balance > 0 && (
                        <button
                          onClick={() => handlePay(inv.id, balance)}
                          className="text-xs bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-md font-semibold hover:bg-indigo-100 transition flex items-center gap-1"
                        >
                          <CreditCard className="w-3.5 h-3.5" />
                          Record Pay
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
  );
};

import React from 'react';
import { CheckCircle2, Clock, AlertTriangle, CreditCard, Printer } from 'lucide-react';

export const Invoices: React.FC = () => {

  const invoices = [
    {
      id: '1',
      number: 'INV-2026-0001',
      customer: 'Acme Corporation',
      period: 'Oct 1 – Oct 31, 2026',
      total: 669.75,
      paid: 669.75,
      status: 'paid',
      dueDate: '2026-10-15',
      isOverdue: false,
    },
    {
      id: '2',
      number: 'INV-2026-0002',
      customer: 'Nexus Global Tech',
      period: 'Oct 1 – Oct 31, 2026',
      total: 1100.00,
      paid: 500.00,
      status: 'confirmed',
      dueDate: '2026-10-20',
      isOverdue: true,
    },
    {
      id: '3',
      number: 'INV-2026-0003',
      customer: 'Solaria Retail Ltd',
      period: 'Oct 1 – Oct 31, 2026',
      total: 245.00,
      paid: 0.00,
      status: 'confirmed',
      dueDate: '2026-11-10',
      isOverdue: false,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Invoices & Collections</h1>
          <p className="text-sm text-slate-500">
            Immutable invoice snapshots with automatic overdue derivation and append-only payment recording.
          </p>
        </div>
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
            {invoices.map((inv) => (
              <tr key={inv.id} className="hover:bg-slate-50/60 transition">
                <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">{inv.number}</td>
                <td className="py-3.5 px-4 font-medium text-slate-900">{inv.customer}</td>
                <td className="py-3.5 px-4 text-xs text-slate-500">{inv.period}</td>
                <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">
                  ${inv.total.toFixed(2)}
                </td>
                <td className="py-3.5 px-4 text-right font-mono">
                  <span className={inv.paid >= inv.total ? 'text-emerald-700 font-semibold' : 'text-slate-700'}>
                    ${inv.paid.toFixed(2)}
                  </span>
                  {inv.total > inv.paid && (
                    <div className="text-[11px] text-amber-600 font-medium">
                      Due: ${(inv.total - inv.paid).toFixed(2)}
                    </div>
                  )}
                </td>
                <td className="py-3.5 px-4 text-xs font-medium text-slate-600">{inv.dueDate}</td>
                <td className="py-3.5 px-4">
                  {inv.status === 'paid' ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                      <CheckCircle2 className="w-3 h-3" />
                      Paid
                    </span>
                  ) : inv.isOverdue ? (
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
                    <button
                      title="Print / View PDF"
                      className="p-1 text-slate-400 hover:text-slate-700 transition"
                    >
                      <Printer className="w-4 h-4" />
                    </button>
                    {inv.status !== 'paid' && (
                      <button className="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded font-semibold hover:bg-indigo-100 transition flex items-center gap-1">
                        <CreditCard className="w-3 h-3" />
                        Record Pay
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};


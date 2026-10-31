import React from 'react';
import { Plus, CheckCircle, Clock, Pause } from 'lucide-react';

export const Subscriptions: React.FC = () => {

  const subscriptions = [
    {
      id: '1',
      number: 'SUB-2026-0001',
      customer: 'Acme Corporation',
      plan: 'Standard Business Monthly',
      status: 'active',
      cadence: 'Monthly',
      amount: '$669.75',
      nextBilling: '2026-11-01',
    },
    {
      id: '2',
      number: 'SUB-2026-0002',
      customer: 'Nexus Global Tech',
      plan: 'Enterprise Annual Plan',
      status: 'quotation',
      cadence: 'Yearly',
      amount: '$1,320.00',
      nextBilling: 'Pending Acceptance',
    },
    {
      id: '3',
      number: 'SUB-2026-0003',
      customer: 'Solaria Retail Ltd',
      plan: 'Standard Business Monthly',
      status: 'paused',
      cadence: 'Monthly',
      amount: '$245.00',
      nextBilling: 'Paused (Resume allowed)',
    },
  ];

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
            <CheckCircle className="w-3 h-3" />
            Active
          </span>
        );
      case 'quotation':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
            <Clock className="w-3 h-3" />
            Quotation
          </span>
        );
      case 'paused':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
            <Pause className="w-3 h-3" />
            Paused
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Subscriptions & Quotations</h1>
          <p className="text-sm text-slate-500">
            Lifecycle state flow: Draft → Quotation → Confirmed → Active → Closed.
          </p>
        </div>
        <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-2 shadow-xs">
          <Plus className="w-4 h-4" />
          Create Quote / Subscription
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
              <th className="py-3 px-4">Subscription #</th>
              <th className="py-3 px-4">Customer</th>
              <th className="py-3 px-4">Plan & Cadence</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4 text-right">Amount</th>
              <th className="py-3 px-4">Next Billing Date</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {subscriptions.map((s) => (
              <tr key={s.id} className="hover:bg-slate-50/60 transition">
                <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">{s.number}</td>
                <td className="py-3.5 px-4 font-medium text-slate-900">{s.customer}</td>
                <td className="py-3.5 px-4">
                  <div className="text-slate-800 font-medium">{s.plan}</div>
                  <div className="text-xs text-slate-400">{s.cadence}</div>
                </td>
                <td className="py-3.5 px-4">{getStatusBadge(s.status)}</td>
                <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">{s.amount}</td>
                <td className="py-3.5 px-4 text-xs font-medium text-slate-600">{s.nextBilling}</td>
                <td className="py-3.5 px-4 text-right">
                  <button className="text-xs text-indigo-600 font-semibold hover:text-indigo-800">
                    Manage
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};


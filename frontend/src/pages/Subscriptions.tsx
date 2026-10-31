import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Plus, CheckCircle, Clock, Pause, RefreshCw } from 'lucide-react';

interface SubItem {
  id: string;
  subscription_number: string;
  customer_name: string;
  plan_name: string;
  status: string;
  total_amount: number;
  next_billing_date?: string;
  lines: any[];
}

export const Subscriptions: React.FC = () => {
  const [subscriptions, setSubscriptions] = useState<SubItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isLive, setIsLive] = useState<boolean>(false);

  const fetchSubscriptions = async () => {
    setLoading(true);
    try {
      const data = await api.getSubscriptions();
      setSubscriptions(data);
      setIsLive(true);
    } catch {
      // Fallback
      setSubscriptions([
        {
          id: '1',
          subscription_number: 'SUB-2026-0001',
          customer_name: 'Acme Corporation',
          plan_name: 'Standard Business Monthly',
          status: 'active',
          total_amount: 905.00,
          next_billing_date: '2026-11-01',
          lines: [],
        },
      ]);
      setIsLive(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscriptions();
  }, []);

  const handlePause = async (id: string) => {
    try {
      await api.pauseSubscription(id);
      await fetchSubscriptions();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleResume = async (id: string) => {
    try {
      await api.resumeSubscription(id);
      await fetchSubscriptions();
    } catch (e: any) {
      alert(e.message);
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
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Subscriptions & Quotations</h1>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                isLive ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {isLive ? '● Live API Data' : 'Cached Baseline'}
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Lifecycle state flow: Draft → Quotation → Confirmed → Active → Closed.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchSubscriptions}
            className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 transition"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-2 shadow-xs">
            <Plus className="w-4 h-4" />
            Create Quote
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
              <th className="py-3 px-4">Subscription #</th>
              <th className="py-3 px-4">Customer</th>
              <th className="py-3 px-4">Plan</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4 text-right">Amount</th>
              <th className="py-3 px-4">Next Billing Date</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {subscriptions.map((s) => (
              <tr key={s.id} className="hover:bg-slate-50/60 transition">
                <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">{s.subscription_number}</td>
                <td className="py-3.5 px-4 font-medium text-slate-900">{s.customer_name}</td>
                <td className="py-3.5 px-4 text-slate-800 font-medium">{s.plan_name}</td>
                <td className="py-3.5 px-4">{getStatusBadge(s.status)}</td>
                <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">
                  ${Number(s.total_amount).toFixed(2)}
                </td>
                <td className="py-3.5 px-4 text-xs font-medium text-slate-600">{s.next_billing_date || 'N/A'}</td>
                <td className="py-3.5 px-4 text-right">
                  {s.status === 'active' ? (
                    <button
                      onClick={() => handlePause(s.id)}
                      className="text-xs text-amber-600 font-semibold hover:text-amber-800"
                    >
                      Pause
                    </button>
                  ) : s.status === 'paused' ? (
                    <button
                      onClick={() => handleResume(s.id)}
                      className="text-xs text-emerald-600 font-semibold hover:text-emerald-800"
                    >
                      Resume
                    </button>
                  ) : (
                    <span className="text-xs text-slate-400">Locked</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

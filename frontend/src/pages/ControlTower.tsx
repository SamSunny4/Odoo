import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Radio, AlertCircle, CheckCircle2, Sparkles, Lock } from 'lucide-react';

interface SimulatedItem {
  id: string;
  subscriptionNumber: string;
  customerName: string;
  planName: string;
  expectedSubtotal: number;
  expectedTax: number;
  expectedDiscount: number;
  expectedTotal: number;
  priorTotal: number;
  varianceReasons: string[];
  warnings: string[];
  status: 'pending' | 'flagged' | 'approved' | 'skipped';
}

const SAMPLE_BATCH: SimulatedItem[] = [
  {
    id: '1',
    subscriptionNumber: 'SUB-2026-0001',
    customerName: 'Acme Corporation',
    planName: 'Standard Monthly (Odoo Brand + Addon)',
    expectedSubtotal: 705.00,
    expectedTax: 70.50,
    expectedDiscount: 105.75,
    expectedTotal: 669.75,
    priorTotal: 669.75,
    varianceReasons: ['Normal renewal'],
    warnings: [],
    status: 'approved',
  },
  {
    id: '2',
    subscriptionNumber: 'SUB-2026-0014',
    customerName: 'Nexus Global Tech',
    planName: 'Standard Monthly (Core ERP 10 Seats)',
    expectedSubtotal: 1200.00,
    expectedTax: 120.00,
    expectedDiscount: 0.00,
    expectedTotal: 1320.00,
    priorTotal: 1100.00,
    varianceReasons: ['Quantity increased (+2 seats)', 'Promotional discount expired'],
    warnings: ['Promotional discount expired this billing cycle'],
    status: 'flagged',
  },
  {
    id: '3',
    subscriptionNumber: 'SUB-2026-0029',
    customerName: 'Solaria Retail Ltd',
    planName: 'Enterprise Annual Plan',
    expectedSubtotal: 2000.00,
    expectedTax: 200.00,
    expectedDiscount: 300.00,
    expectedTotal: 1900.00,
    priorTotal: 1900.00,
    varianceReasons: ['Annual renewal'],
    warnings: ['Missing Customer VAT / Tax ID on file'],
    status: 'flagged',
  },
];

export const ControlTower: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user.role === 'admin';
  const [items] = useState<SimulatedItem[]>(SAMPLE_BATCH);
  const [committed, setCommitted] = useState(false);

  const totalProjected = items.reduce((acc, i) => acc + i.expectedTotal, 0);

  const handleCommit = () => {
    if (!isAdmin) return;
    setCommitted(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <Radio className="w-6 h-6 text-indigo-600 animate-pulse" />
              Billing Control Tower
            </h1>
            <span className="bg-indigo-100 text-indigo-700 text-xs px-2 py-0.5 rounded-full font-semibold flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              Differentiating Feature
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Pre-flight audit engine: inspect calculated invoices, explain financial variances, and resolve warnings before issuing batch.
          </p>
        </div>

        {/* Action Commit Button with Permission Guard */}
        <div>
          {isAdmin ? (
            <button
              onClick={handleCommit}
              disabled={committed}
              className={`px-4 py-2 rounded-lg text-sm font-semibold text-white shadow-xs transition flex items-center gap-2 ${
                committed
                  ? 'bg-emerald-600 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-700'
              }`}
            >
              {committed ? (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Batch Committed (Invoices Issued)
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Commit Approved Batch ({items.length})
                </>
              )}
            </button>
          ) : (
            <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 text-amber-800 px-3 py-1.5 rounded-lg text-xs font-medium">
              <Lock className="w-3.5 h-3.5 text-amber-600" />
              <span>Staff can preview only (Admin required to commit)</span>
            </div>
          )}
        </div>
      </div>

      {/* Batch Summary Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs grid grid-cols-2 sm:grid-cols-4 gap-4 text-center sm:text-left">
        <div>
          <div className="text-xs text-slate-400 font-semibold uppercase">Billing Period</div>
          <div className="text-base font-bold text-slate-800">Nov 1 – Nov 30, 2026</div>
        </div>
        <div>
          <div className="text-xs text-slate-400 font-semibold uppercase">Subscriptions Due</div>
          <div className="text-base font-bold text-slate-800">{items.length} Evaluated</div>
        </div>
        <div>
          <div className="text-xs text-slate-400 font-semibold uppercase">Total Projected Run</div>
          <div className="text-base font-bold text-indigo-600">${totalProjected.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-xs text-slate-400 font-semibold uppercase">Warnings Flagged</div>
          <div className="text-base font-bold text-amber-600">2 Items Require Review</div>
        </div>
      </div>

      {/* Per-Subscription Items Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="font-semibold text-slate-800 text-sm">Batch Line-Level Audit Items</h3>
          <span className="text-xs text-slate-400">Idempotency key enforced on commit</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                <th className="py-3 px-4">Subscription</th>
                <th className="py-3 px-4">Customer & Plan</th>
                <th className="py-3 px-4 text-right">Calculation (Sub - Disc + Tax)</th>
                <th className="py-3 px-4 text-right">Expected Total</th>
                <th className="py-3 px-4">Prior Variance</th>
                <th className="py-3 px-4">Audit Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/60 transition">
                  <td className="py-3 px-4 font-mono font-medium text-xs text-indigo-700">
                    {item.subscriptionNumber}
                  </td>
                  <td className="py-3 px-4">
                    <div className="font-semibold text-slate-900">{item.customerName}</div>
                    <div className="text-xs text-slate-500">{item.planName}</div>
                  </td>
                  <td className="py-3 px-4 text-right text-xs font-mono text-slate-600">
                    ${item.expectedSubtotal.toFixed(2)} - ${item.expectedDiscount.toFixed(2)} + ${item.expectedTax.toFixed(2)}
                  </td>
                  <td className="py-3 px-4 text-right font-semibold text-slate-900 font-mono">
                    ${item.expectedTotal.toFixed(2)}
                  </td>
                  <td className="py-3 px-4">
                    {item.expectedTotal !== item.priorTotal ? (
                      <div>
                        <span className="text-xs font-semibold text-amber-700">
                          Δ ${(item.expectedTotal - item.priorTotal).toFixed(2)} vs prior
                        </span>
                        <div className="text-[11px] text-slate-500">{item.varianceReasons.join(', ')}</div>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400">No variance</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    {item.warnings.length > 0 ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                        <AlertCircle className="w-3 h-3" />
                        Flagged
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">
                        <CheckCircle2 className="w-3 h-3" />
                        Clean
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};


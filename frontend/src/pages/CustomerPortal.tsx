import React from 'react';
import { useAuth } from '../context/AuthContext';
import { CheckCircle2, Download } from 'lucide-react';

export const CustomerPortal: React.FC<{ activeTab?: string }> = ({ activeTab = 'portal-subscriptions' }) => {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-700 font-bold text-lg">
            AC
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">{user.companyName || 'Acme Corporation'}</h1>
            <p className="text-xs text-slate-500">
              Customer Portal • Signed in as <span className="font-semibold">{user.email}</span> (Account Owner)
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
            Account in Good Standing
          </span>
        </div>
      </div>

      {activeTab === 'portal-subscriptions' && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-slate-900">Your Active Subscriptions</h2>
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono font-semibold text-indigo-700">SUB-2026-0001</span>
                <span className="bg-emerald-100 text-emerald-800 text-xs px-2 py-0.5 rounded-full font-medium">Active</span>
              </div>
              <h3 className="text-base font-bold text-slate-900 mt-1">Standard Business Monthly</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Includes: Brightloop Core ERP (Brand: Odoo) + Advanced Analytics Add-on
              </p>
              <div className="text-xs text-slate-400 mt-2 flex items-center gap-4">
                <span>Renews on: <strong>Nov 1, 2026</strong></span>
                <span>Billing Cadence: <strong>Monthly ($669.75)</strong></span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition">
                Manage Add-ons
              </button>
              <button className="px-3 py-1.5 text-xs font-semibold text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg transition">
                Request Pause
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'portal-invoices' && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-slate-900">Your Invoices & Receipts</h2>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <table className="w-full text-left border-collapse text-sm">
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
                <tr className="hover:bg-slate-50/60 transition">
                  <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">INV-2026-0001</td>
                  <td className="py-3.5 px-4 text-xs text-slate-600">Oct 1 – Oct 31, 2026</td>
                  <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">$669.75</td>
                  <td className="py-3.5 px-4">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                      <CheckCircle2 className="w-3 h-3" />
                      Paid
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <button className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1">
                      <Download className="w-3.5 h-3.5" />
                      Download PDF
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'portal-profile' && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs max-w-2xl space-y-4">
          <h2 className="text-lg font-bold text-slate-900">Company Billing Profile</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Company Name</label>
              <div className="font-medium text-slate-800">Acme Corporation</div>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Tax ID / VAT</label>
              <div className="font-medium text-slate-800">US-TAX-987654321</div>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-semibold text-slate-400 uppercase">Billing Address</label>
              <div className="font-medium text-slate-800">100 Innovation Blvd, Austin, TX 78701, United States</div>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Billing Currency</label>
              <div className="font-medium text-slate-800">USD ($)</div>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Registered Email</label>
              <div className="font-medium text-slate-800">{user.email}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


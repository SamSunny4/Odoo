import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import type { InvoiceApiItem, PortalProfile, SubscriptionApiItem } from '../services/api';
import { CheckCircle2, Download, RefreshCw } from 'lucide-react';

export const CustomerPortal: React.FC<{ activeTab?: string }> = ({ activeTab = 'portal-subscriptions' }) => {
  const { user } = useAuth();
  const [subscriptions, setSubscriptions] = useState<SubscriptionApiItem[]>([]);
  const [invoices, setInvoices] = useState<InvoiceApiItem[]>([]);
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPortalData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [subs, invs, prof] = await Promise.all([
        api.getPortalSubscriptions(),
        api.getPortalInvoices(),
        api.getPortalProfile(),
      ]);
      setSubscriptions(subs);
      setInvoices(invs);
      setProfile(prof);
      setIsLive(true);
    } catch (reason) {
      setSubscriptions([]);
      setInvoices([]);
      setProfile(null);
      setIsLive(false);
      setError(reason instanceof Error ? reason.message : 'Could not load your account data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPortalData();
  }, [user?.id]);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-700 font-bold text-lg">
            AC
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900">{profile?.company_name || user?.companyName || 'Customer account'}</h1>
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                  isLive ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {isLive ? '● Live Account Data' : 'No live data'}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Customer Portal • Signed in as <span className="font-semibold">{user?.email || 'Customer'}</span> (Derived Session Scope)
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchPortalData}
            className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 transition"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && <div role="alert" className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{error}</div>}

      {activeTab === 'portal-subscriptions' && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-slate-900">Your Active Subscriptions</h2>
          {!loading && subscriptions.length === 0 && <div className="bg-white rounded-xl border border-slate-200 p-6 text-sm text-slate-500">No subscriptions to display.</div>}
          {subscriptions.map((sub) => (
            <div
              key={sub.id}
              className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono font-semibold text-indigo-700">{sub.subscription_number}</span>
                  <span className="bg-emerald-100 text-emerald-800 text-xs px-2 py-0.5 rounded-full font-medium capitalize">
                    {sub.status}
                  </span>
                </div>
                <h3 className="text-base font-bold text-slate-900 mt-1">{sub.plan_name}</h3>
                <div className="text-xs text-slate-500 mt-2 flex items-center gap-4">
                  <span>Renews on: <strong>{sub.next_billing_date || 'Next Cycle'}</strong></span>
                  <span>Amount: <strong>${Number(sub.total_amount).toFixed(2)}</strong></span>
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
          ))}
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
                {invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50/60 transition">
                    <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">{inv.invoice_number}</td>
                    <td className="py-3.5 px-4 text-xs text-slate-600">
                      {inv.billing_period_start} – {inv.billing_period_end}
                    </td>
                    <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">
                      ${Number(inv.total_amount).toFixed(2)}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 capitalize">
                        <CheckCircle2 className="w-3 h-3" />
                        {inv.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1">
                        <Download className="w-3.5 h-3.5" />
                        Download PDF
                      </button>
                    </td>
                  </tr>
                ))}
                {!loading && invoices.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-slate-500">No invoices to display.</td></tr>}
                {loading && <tr><td colSpan={5} className="p-8 text-center text-slate-500">Loading invoices…</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'portal-profile' && profile && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs max-w-2xl space-y-4">
          <h2 className="text-lg font-bold text-slate-900">Company Billing Profile</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Company Name</label>
              <div className="font-medium text-slate-800">{profile.company_name}</div>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Tax ID / VAT</label>
              <div className="font-medium text-slate-800">{profile.tax_id || 'None'}</div>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-semibold text-slate-400 uppercase">Billing Address</label>
              <div className="font-medium text-slate-800">{profile.billing_address || 'No billing address on file'}</div>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Billing Currency</label>
              <div className="font-medium text-slate-800">{profile.currency}</div>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Registered Email</label>
              <div className="font-medium text-slate-800">{profile.billing_email}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

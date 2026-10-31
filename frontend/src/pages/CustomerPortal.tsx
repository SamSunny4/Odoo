import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { api, InvoiceApiItem, PortalProfile, SubscriptionApiItem } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { SearchAndFilterBar, FilterOption, SortOption } from '../components/common/SearchAndFilterBar';
import { PaginationControls } from '../components/common/PaginationControls';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { CheckCircle2, Download, RefreshCw, CalendarDays, Receipt, Building } from 'lucide-react';

interface CustomerPortalProps {
  activeTab?: string;
  onNavigate?: (tabKey: string) => void;
}

const SUBSCRIPTION_STATUS_OPTIONS: FilterOption[] = [
  { label: 'Active', value: 'active' },
  { label: 'Quotation', value: 'quotation' },
  { label: 'Confirmed', value: 'confirmed' },
  { label: 'Paused', value: 'paused' },
  { label: 'Closed', value: 'closed' },
  { label: 'Draft', value: 'draft' },
];

const SUBSCRIPTION_SORT_OPTIONS: SortOption[] = [
  { label: 'Newest First', sortBy: 'created_at', sortOrder: 'desc' },
  { label: 'Oldest First', sortBy: 'created_at', sortOrder: 'asc' },
  { label: 'Subscription # (A-Z)', sortBy: 'subscription_number', sortOrder: 'asc' },
  { label: 'Next Billing Date', sortBy: 'next_billing_date', sortOrder: 'asc' },
];

const INVOICE_STATUS_OPTIONS: FilterOption[] = [
  { label: 'Confirmed', value: 'confirmed' },
  { label: 'Paid', value: 'paid' },
  { label: 'Overdue', value: 'overdue' },
  { label: 'Draft', value: 'draft' },
  { label: 'Cancelled', value: 'cancelled' },
];

const INVOICE_SORT_OPTIONS: SortOption[] = [
  { label: 'Issue Date (Newest)', sortBy: 'issue_date', sortOrder: 'desc' },
  { label: 'Issue Date (Oldest)', sortBy: 'issue_date', sortOrder: 'asc' },
  { label: 'Due Date (Earliest)', sortBy: 'due_date', sortOrder: 'asc' },
  { label: 'Total Amount (High to Low)', sortBy: 'total_amount', sortOrder: 'desc' },
  { label: 'Outstanding Balance', sortBy: 'outstanding_balance', sortOrder: 'desc' },
];

export const CustomerPortal: React.FC<CustomerPortalProps> = ({
  activeTab = 'portal-subscriptions',
  onNavigate,
}) => {
  const { user } = useAuth();
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Subscriptions Tab State
  const [subscriptions, setSubscriptions] = useState<SubscriptionApiItem[]>([]);
  const [subsLoading, setSubsLoading] = useState<boolean>(true);
  const [subsPage, setSubsPage] = useState<number>(1);
  const [subsPageSize, setSubsPageSize] = useState<number>(5);
  const [subsTotal, setSubsTotal] = useState<number>(0);
  const [subsTotalPages, setSubsTotalPages] = useState<number>(1);
  const [subsSearch, setSubsSearch] = useState<string>('');
  const [subsStatus, setSubsStatus] = useState<string>('all');
  const [subsSort, setSubsSort] = useState<string>('created_at-desc');

  // Invoices Tab State
  const [invoices, setInvoices] = useState<InvoiceApiItem[]>([]);
  const [invsLoading, setInvsLoading] = useState<boolean>(true);
  const [invsPage, setInvsPage] = useState<number>(1);
  const [invsPageSize, setInvsPageSize] = useState<number>(5);
  const [invsTotal, setInvsTotal] = useState<number>(0);
  const [invsTotalPages, setInvsTotalPages] = useState<number>(1);
  const [invsSearch, setInvsSearch] = useState<string>('');
  const [invsStatus, setInvsStatus] = useState<string>('all');
  const [invsSort, setInvsSort] = useState<string>('issue_date-desc');

  const fetchProfile = useCallback(async () => {
    try {
      const prof = await api.getPortalProfile();
      setProfile(prof);
      setIsLive(true);
    } catch {
      // Non-fatal
    }
  }, []);

  const fetchSubscriptions = useCallback(async () => {
    setSubsLoading(true);
    const [sortBy, sortOrder] = subsSort.split('-') as [string, 'asc' | 'desc'];
    try {
      const data = await api.getPortalSubscriptions({
        page: subsPage,
        pageSize: subsPageSize,
        search: subsSearch || undefined,
        status: subsStatus !== 'all' ? subsStatus : undefined,
        sortBy,
        sortOrder,
      });
      setSubscriptions(data.items);
      setSubsTotal(data.total);
      setSubsTotalPages(data.totalPages);
      setIsLive(true);
    } catch (err) {
      setSubscriptions([]);
      setError(err instanceof Error ? err.message : 'Could not load subscriptions.');
    } finally {
      setSubsLoading(false);
    }
  }, [subsPage, subsPageSize, subsSearch, subsStatus, subsSort]);

  const fetchInvoices = useCallback(async () => {
    setInvsLoading(true);
    const [sortBy, sortOrder] = invsSort.split('-') as [string, 'asc' | 'desc'];
    try {
      const data = await api.getPortalInvoices({
        page: invsPage,
        pageSize: invsPageSize,
        search: invsSearch || undefined,
        status: invsStatus !== 'all' ? invsStatus : undefined,
        sortBy,
        sortOrder,
      });
      setInvoices(data.items);
      setInvsTotal(data.total);
      setInvsTotalPages(data.totalPages);
      setIsLive(true);
    } catch (err) {
      setInvoices([]);
      setError(err instanceof Error ? err.message : 'Could not load invoices.');
    } finally {
      setInvsLoading(false);
    }
  }, [invsPage, invsPageSize, invsSearch, invsStatus, invsSort]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile, user?.id]);

  useEffect(() => {
    if (activeTab === 'portal-subscriptions') {
      fetchSubscriptions();
    } else if (activeTab === 'portal-invoices') {
      fetchInvoices();
    }
  }, [activeTab, fetchSubscriptions, fetchInvoices]);

  const handleRefreshAll = () => {
    fetchProfile();
    if (activeTab === 'portal-subscriptions') fetchSubscriptions();
    if (activeTab === 'portal-invoices') fetchInvoices();
  };

  const getTabTitle = () => {
    if (activeTab === 'portal-invoices') return 'My Invoices & Receipts';
    if (activeTab === 'portal-profile') return 'Company & Billing Profile';
    return 'My Subscriptions';
  };

  return (
    <div className="space-y-6">
      {/* Account Shell Header */}
      <PageHeader
        title={profile?.company_name || user?.companyName || 'Customer Portal'}
        subtitle={`Signed in as ${user?.email || 'Customer'} (Scoped strictly to your company account)`}
        breadcrumbs={[
          { label: 'Customer Portal', tabKey: 'portal-subscriptions' },
          { label: getTabTitle() },
        ]}
        onSelectTab={onNavigate}
        badge={
          <span
            className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
              isLive ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
            }`}
          >
            {isLive ? '● Live Account Data' : 'Connecting...'}
          </span>
        }
        actions={
          <button
            onClick={handleRefreshAll}
            className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
            title="Refresh"
            aria-label="Refresh customer data"
          >
            <RefreshCw className={`w-4 h-4 ${subsLoading || invsLoading ? 'animate-spin' : ''}`} />
          </button>
        }
      />

      {error && <ErrorState message={error} onRetry={handleRefreshAll} />}

      {/* Subscriptions Tab */}
      {activeTab === 'portal-subscriptions' && (
        <div className="space-y-4">
          <SearchAndFilterBar
            searchQuery={subsSearch}
            onSearchChange={(q) => {
              setSubsSearch(q);
              setSubsPage(1);
            }}
            searchPlaceholder="Search your subscriptions by #..."
            statusFilter={subsStatus}
            onStatusChange={(value) => {
              setSubsStatus(value);
              setSubsPage(1);
            }}
            statusOptions={SUBSCRIPTION_STATUS_OPTIONS}
            sortValue={subsSort}
            onSortChange={(value) => {
              setSubsSort(value);
              setSubsPage(1);
            }}
            sortOptions={SUBSCRIPTION_SORT_OPTIONS}
            onReset={() => {
              setSubsSearch('');
              setSubsStatus('all');
              setSubsSort('created_at-desc');
              setSubsPage(1);
            }}
          />

          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            {subsLoading ? (
              <LoadingState message="Loading your subscriptions..." rows={3} />
            ) : subscriptions.length === 0 ? (
              <EmptyState
                title="No subscriptions found"
                description="There are currently no active subscriptions associated with your account."
                icon={<CalendarDays className="w-6 h-6" />}
              />
            ) : (
              <div className="divide-y divide-slate-200">
                {subscriptions.map((sub) => (
                  <div
                    key={sub.id}
                    className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-50/60 transition"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono font-semibold text-indigo-700">
                          {sub.subscription_number}
                        </span>
                        <span className="bg-emerald-100 text-emerald-800 text-xs px-2 py-0.5 rounded-full font-medium capitalize">
                          {sub.status}
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-slate-900 mt-1">{sub.plan_name}</h3>
                      <div className="text-xs text-slate-500 mt-2 flex items-center gap-4 flex-wrap">
                        <span>
                          Renews on: <strong>{sub.next_billing_date || 'Next Cycle'}</strong>
                        </span>
                        <span>
                          Amount: <strong>${Number(sub.total_amount).toFixed(2)}</strong>
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-start md:self-auto">
                      <button className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition">
                        Manage Add-ons
                      </button>
                      <button className="px-3 py-1.5 text-xs font-semibold text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg transition">
                        Request Pause
                      </button>
                    </div>
                  </div>
                ))}

                <PaginationControls
                  page={subsPage}
                  pageSize={subsPageSize}
                  total={subsTotal}
                  totalPages={subsTotalPages}
                  onPageChange={setSubsPage}
                  onPageSizeChange={(sz) => {
                    setSubsPageSize(sz);
                    setSubsPage(1);
                  }}
                  pageSizeOptions={[5, 10, 20]}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Invoices Tab */}
      {activeTab === 'portal-invoices' && (
        <div className="space-y-4">
          <SearchAndFilterBar
            searchQuery={invsSearch}
            onSearchChange={(q) => {
              setInvsSearch(q);
              setInvsPage(1);
            }}
            searchPlaceholder="Search your invoices by #..."
            statusFilter={invsStatus}
            onStatusChange={(value) => {
              setInvsStatus(value);
              setInvsPage(1);
            }}
            statusOptions={INVOICE_STATUS_OPTIONS}
            sortValue={invsSort}
            onSortChange={(value) => {
              setInvsSort(value);
              setInvsPage(1);
            }}
            sortOptions={INVOICE_SORT_OPTIONS}
            onReset={() => {
              setInvsSearch('');
              setInvsStatus('all');
              setInvsSort('issue_date-desc');
              setInvsPage(1);
            }}
          />

          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            {invsLoading ? (
              <LoadingState message="Loading your billing documents..." rows={3} />
            ) : invoices.length === 0 ? (
              <EmptyState
                title="No invoices found"
                description="There are no billing documents or invoices for your account."
                icon={<Receipt className="w-6 h-6" />}
              />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-sm min-w-[550px]">
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
                          <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">
                            {inv.invoice_number}
                          </td>
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
                            <button
                              onClick={() => alert(`Downloading PDF for invoice ${inv.invoice_number}...`)}
                              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1 transition"
                            >
                              <Download className="w-3.5 h-3.5" />
                              PDF
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <PaginationControls
                  page={invsPage}
                  pageSize={invsPageSize}
                  total={invsTotal}
                  totalPages={invsTotalPages}
                  onPageChange={setInvsPage}
                  onPageSizeChange={(sz) => {
                    setInvsPageSize(sz);
                    setInvsPage(1);
                  }}
                  pageSizeOptions={[5, 10, 20]}
                />
              </>
            )}
          </div>
        </div>
      )}

      {/* Profile Tab */}
      {activeTab === 'portal-profile' && profile && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs max-w-2xl space-y-5">
          <div className="flex items-center gap-3 pb-3 border-b border-slate-200">
            <Building className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Company Billing Profile</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Company Name</span>
              <div className="font-medium text-slate-800">{profile.company_name}</div>
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Tax ID / VAT</span>
              <div className="font-medium text-slate-800">{profile.tax_id || 'None'}</div>
            </div>
            <div className="sm:col-span-2">
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Billing Address</span>
              <div className="font-medium text-slate-800">
                {profile.billing_address || 'No billing address on file'}
              </div>
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Billing Currency</span>
              <div className="font-medium text-slate-800">{profile.currency}</div>
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase block mb-1">Registered Email</span>
              <div className="font-medium text-slate-800">{profile.billing_email}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

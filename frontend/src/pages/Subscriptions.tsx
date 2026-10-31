import React, { useEffect, useState, useCallback } from 'react';
import { api, SubscriptionApiItem } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { SearchAndFilterBar, FilterOption, SortOption } from '../components/common/SearchAndFilterBar';
import { PaginationControls } from '../components/common/PaginationControls';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { AlertBanner } from '../components/common/AlertBanner';
import { Plus, CheckCircle, Clock, Pause, RefreshCw, XCircle } from 'lucide-react';

const STATUS_OPTIONS: FilterOption[] = [
  { label: 'Active', value: 'active' },
  { label: 'Quotation', value: 'quotation' },
  { label: 'Paused', value: 'paused' },
  { label: 'Closed', value: 'closed' },
  { label: 'Draft', value: 'draft' },
];

const SORT_OPTIONS: SortOption[] = [
  { label: 'Newest First', sortBy: 'created_at', sortOrder: 'desc' },
  { label: 'Oldest First', sortBy: 'created_at', sortOrder: 'asc' },
  { label: 'Subscription # (A-Z)', sortBy: 'subscription_number', sortOrder: 'asc' },
  { label: 'Next Billing Date', sortBy: 'next_billing_date', sortOrder: 'asc' },
];

export const Subscriptions: React.FC = () => {
  const [subscriptions, setSubscriptions] = useState<SubscriptionApiItem[]>([]);
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
  const [sortValue, setSortValue] = useState<string>('created_at-desc');

  const fetchSubscriptions = useCallback(async () => {
    setLoading(true);
    setError(null);

    const [sortBy, sortOrder] = sortValue.split('-') as [string, 'asc' | 'desc'];

    try {
      const data = await api.getSubscriptions({
        page,
        pageSize,
        search: searchQuery || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        sortBy,
        sortOrder,
      });

      setSubscriptions(data.items);
      setTotal(data.total);
      setTotalPages(data.totalPages);
      setIsLive(true);
    } catch (reason) {
      setSubscriptions([]);
      setIsLive(false);
      setError(reason instanceof Error ? reason.message : 'Could not load subscriptions.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, searchQuery, statusFilter, sortValue]);

  useEffect(() => {
    fetchSubscriptions();
  }, [fetchSubscriptions]);

  const handlePause = async (id: string, num: string) => {
    try {
      await api.pauseSubscription(id);
      setFeedback({ type: 'success', message: `Subscription ${num} paused successfully.` });
      await fetchSubscriptions();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Could not pause the subscription.',
      });
    }
  };

  const handleResume = async (id: string, num: string) => {
    try {
      await api.resumeSubscription(id);
      setFeedback({ type: 'success', message: `Subscription ${num} resumed successfully.` });
      await fetchSubscriptions();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Could not resume the subscription.',
      });
    }
  };

  const handleResetFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setSortValue('created_at-desc');
    setPage(1);
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
      case 'closed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-700">
            <XCircle className="w-3 h-3" />
            Closed
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
        title="Subscriptions & Quotations"
        subtitle="Manage recurring customer subscriptions, quotations, and lifecycle statuses."
        breadcrumbs={[
          { label: 'Brightloop' },
          { label: 'Operations' },
          { label: 'Subscriptions & Quotes' },
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
          <div className="flex items-center gap-2">
            <button
              onClick={fetchSubscriptions}
              className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
              title="Refresh"
              aria-label="Refresh subscriptions"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button className="px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-xs sm:text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-1.5 shadow-xs">
              <Plus className="w-4 h-4" />
              <span>Create Quote</span>
            </button>
          </div>
        }
      />

      {feedback && (
        <AlertBanner
          type={feedback.type}
          message={feedback.message}
          onClose={() => setFeedback(null)}
        />
      )}

      {error && <ErrorState message={error} onRetry={fetchSubscriptions} />}

      <SearchAndFilterBar
        searchQuery={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          setPage(1);
        }}
        searchPlaceholder="Search by subscription # or customer name..."
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
          <LoadingState message="Loading subscriptions from server..." rows={5} />
        ) : subscriptions.length === 0 ? (
          <EmptyState
            title="No subscriptions match your search"
            description="Try modifying or clearing your filters to see more subscriptions."
            action={{ label: 'Clear Filters', onClick: handleResetFilters }}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm min-w-[650px]">
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
                      <td className="py-3.5 px-4 font-mono font-semibold text-indigo-700">
                        {s.subscription_number}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-900">{s.customer_name}</td>
                      <td className="py-3.5 px-4 text-slate-800 font-medium">{s.plan_name}</td>
                      <td className="py-3.5 px-4">{getStatusBadge(s.status)}</td>
                      <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">
                        ${Number(s.total_amount).toFixed(2)}
                      </td>
                      <td className="py-3.5 px-4 text-xs font-medium text-slate-600">
                        {s.next_billing_date || 'N/A'}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        {s.status === 'active' ? (
                          <button
                            onClick={() => handlePause(s.id, s.subscription_number)}
                            className="text-xs text-amber-600 font-semibold hover:text-amber-800 transition"
                          >
                            Pause
                          </button>
                        ) : s.status === 'paused' ? (
                          <button
                            onClick={() => handleResume(s.id, s.subscription_number)}
                            className="text-xs text-emerald-600 font-semibold hover:text-emerald-800 transition"
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
    </div>
  );
};

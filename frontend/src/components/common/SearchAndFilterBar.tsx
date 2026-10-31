import React from 'react';
import { Search, X, Filter } from 'lucide-react';

export interface FilterOption {
  label: string;
  value: string;
}

export interface SortOption {
  label: string;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
}

interface SearchAndFilterBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchPlaceholder?: string;
  statusFilter?: string;
  onStatusChange?: (status: string) => void;
  statusOptions?: FilterOption[];
  sortValue?: string;
  onSortChange?: (sortValue: string) => void;
  sortOptions?: SortOption[];
  onReset?: () => void;
  children?: React.ReactNode;
}

export const SearchAndFilterBar: React.FC<SearchAndFilterBarProps> = ({
  searchQuery,
  onSearchChange,
  searchPlaceholder = 'Search...',
  statusFilter,
  onStatusChange,
  statusOptions,
  sortValue,
  onSortChange,
  sortOptions,
  onReset,
  children,
}) => {
  const defaultSortValue = sortOptions?.[0]
    ? `${sortOptions[0].sortBy}-${sortOptions[0].sortOrder}`
    : undefined;
  const sortChanged = Boolean(sortValue && defaultSortValue && sortValue !== defaultSortValue);
  const hasActiveFilters = Boolean(
    searchQuery.trim() ||
    (statusFilter && statusFilter !== 'all') ||
    sortChanged
  );

  return (
    <div className="bg-white p-3 sm:p-4 rounded-xl border border-sky-100/90 shadow-2xs space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full pl-9 pr-8 py-2 text-sm border border-slate-200 rounded-lg bg-slate-50/70 focus:bg-white focus:border-sky-400 focus:ring-2 focus:ring-sky-400/20 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition text-slate-800 placeholder-slate-400"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Filter Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {statusOptions && onStatusChange && (
            <div className="flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-slate-400 hidden sm:inline" aria-hidden="true" />
              <select
                value={statusFilter || 'all'}
                onChange={(e) => onStatusChange(e.target.value)}
                className="py-2 px-3 text-xs border border-slate-200 rounded-lg bg-slate-50 text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
                aria-label="Filter by status"
              >
                <option value="all">All Statuses</option>
                {statusOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {sortOptions && onSortChange && (
            <select
              value={sortValue || ''}
              onChange={(e) => onSortChange(e.target.value)}
              className="py-2 px-3 text-xs border border-slate-200 rounded-lg bg-slate-50 text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
              aria-label="Sort by"
            >
              {sortOptions.map((opt, i) => (
                <option key={i} value={`${opt.sortBy}-${opt.sortOrder}`}>
                  Sort: {opt.label}
                </option>
              ))}
            </select>
          )}

          {children}

          {hasActiveFilters && onReset && (
            <button
              onClick={onReset}
              className="px-2.5 py-2 text-xs text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition"
            >
              Reset
            </button>
          )}
        </div>
      </div>
    </div>
  );
};


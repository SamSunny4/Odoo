import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { api, ProductApiItem } from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { SearchAndFilterBar, FilterOption, SortOption } from '../components/common/SearchAndFilterBar';
import { PaginationControls } from '../components/common/PaginationControls';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { Lock, Plus, Tag, RefreshCw } from 'lucide-react';

const TYPE_OPTIONS: FilterOption[] = [
  { label: 'Service', value: 'service' },
  { label: 'Goods', value: 'goods' },
];

const SORT_OPTIONS: SortOption[] = [
  { label: 'Product Name (A-Z)', sortBy: 'name', sortOrder: 'asc' },
  { label: 'Product Name (Z-A)', sortBy: 'name', sortOrder: 'desc' },
  { label: 'Sales Price (High to Low)', sortBy: 'sales_price', sortOrder: 'desc' },
  { label: 'Sales Price (Low to High)', sortBy: 'sales_price', sortOrder: 'asc' },
];

interface CatalogProps {
  onNavigate?: (tabKey: string) => void;
}

export const Catalog: React.FC<CatalogProps> = ({ onNavigate }) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [products, setProducts] = useState<ProductApiItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Pagination & Filters State
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [sortValue, setSortValue] = useState<string>('name-asc');

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError(null);

    const [sortBy, sortOrder] = sortValue.split('-') as [string, 'asc' | 'desc'];

    try {
      const data = await api.getProducts({
        page,
        pageSize,
        search: searchQuery || undefined,
        type: typeFilter !== 'all' ? typeFilter : undefined,
        sortBy,
        sortOrder,
      });

      setProducts(data.items);
      setTotal(data.total);
      setTotalPages(data.totalPages);
      setIsLive(true);
    } catch (reason) {
      setProducts([]);
      setIsLive(false);
      setError(reason instanceof Error ? reason.message : 'Could not load products.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, searchQuery, typeFilter, sortValue]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts, user?.role]);

  const handleResetFilters = () => {
    setSearchQuery('');
    setTypeFilter('all');
    setSortValue('name-asc');
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Products & Variants Catalog"
        subtitle={
          isAdmin
            ? 'Configure products, pricing, and brand variants (e.g. Odoo brand +560).'
            : 'View product catalog and active selling prices (Cost prices restricted to Admin).'
        }
        breadcrumbs={[
          { label: 'Brightloop', tabKey: 'dashboard' },
          { label: 'Catalog & Configuration', tabKey: 'catalog' },
          { label: 'Products & Variants' },
        ]}
        onSelectTab={onNavigate}
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
              onClick={fetchProducts}
              className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 transition"
              title="Refresh from API"
              aria-label="Refresh product catalog"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            {isAdmin && (
              <button className="px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-xs sm:text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-1.5 shadow-xs">
                <Plus className="w-4 h-4" />
                <span>Add Product</span>
              </button>
            )}
          </div>
        }
      />

      {error && <ErrorState message={error} onRetry={fetchProducts} />}

      <SearchAndFilterBar
        searchQuery={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          setPage(1);
        }}
        searchPlaceholder="Search products by name or type..."
        statusFilter={typeFilter}
        onStatusChange={(t) => {
          setTypeFilter(t);
          setPage(1);
        }}
        statusOptions={TYPE_OPTIONS}
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
          <LoadingState message="Loading catalog from server..." rows={5} />
        ) : products.length === 0 ? (
          <EmptyState
            title="No products found"
            description="There are no catalog items matching your search or filters."
            action={{ label: 'Clear Filters', onClick: handleResetFilters }}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm min-w-[650px]">
                <thead>
                  <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                    <th className="py-3 px-4">Product Name</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Variants & Adjustments</th>
                    <th className="py-3 px-4 text-right">Sales Price</th>
                    <th className="py-3 px-4 text-right">Cost Price</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {products.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/60 transition">
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-900">{p.name}</div>
                        {p.notes && <div className="text-xs text-slate-500 mt-0.5">{p.notes}</div>}
                      </td>
                      <td className="py-3.5 px-4 capitalize">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                          {p.type}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        {p.variants && p.variants.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {p.variants.map((v, idx) => (
                              <span
                                key={idx}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100"
                              >
                                <Tag className="w-3 h-3" />
                                {v.name} (+${Number(v.price_adjustment).toFixed(2)})
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">None</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">
                        ${Number(p.sales_price).toFixed(2)}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono">
                        {isAdmin && p.cost_price !== null && p.cost_price !== undefined ? (
                          <span className="text-slate-600 font-medium">
                            ${Number(p.cost_price).toFixed(2)}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-slate-400 italic">
                            <Lock className="w-3 h-3 text-slate-400" />
                            Admin Only
                          </span>
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

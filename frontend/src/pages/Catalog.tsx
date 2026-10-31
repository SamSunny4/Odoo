import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  api,
  ProductApiItem,
  ProductVariantApiItem,
  CreateProductPayload,
  UpdateProductPayload,
} from '../services/api';
import { PageHeader } from '../components/common/PageHeader';
import { SearchAndFilterBar, FilterOption, SortOption } from '../components/common/SearchAndFilterBar';
import { PaginationControls } from '../components/common/PaginationControls';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { AlertBanner } from '../components/common/AlertBanner';
import {
  Lock,
  Plus,
  Tag,
  RefreshCw,
  Edit2,
  Trash2,
  X,
  Layers,
  Sparkles,
} from 'lucide-react';

const TYPE_OPTIONS: FilterOption[] = [
  { label: 'Service', value: 'service' },
  { label: 'Goods', value: 'goods' },
  { label: 'Consumable', value: 'consumable' },
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
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Pagination & Filters State
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [sortValue, setSortValue] = useState<string>('name-asc');

  // Product Modal State
  const [showProductModal, setShowProductModal] = useState<boolean>(false);
  const [editingProduct, setEditingProduct] = useState<ProductApiItem | null>(null);
  const [productForm, setProductForm] = useState<{
    name: string;
    type: string;
    sales_price: string;
    cost_price: string;
    notes: string;
  }>({
    name: '',
    type: 'service',
    sales_price: '',
    cost_price: '',
    notes: '',
  });
  const [productSubmitting, setProductSubmitting] = useState<boolean>(false);
  const [productFormError, setProductFormError] = useState<string | null>(null);

  // Variant Modal State
  const [selectedProductForVariants, setSelectedProductForVariants] = useState<ProductApiItem | null>(null);
  const [variantList, setVariantList] = useState<ProductVariantApiItem[]>([]);
  const [variantLoading, setVariantLoading] = useState<boolean>(false);
  const [variantForm, setVariantForm] = useState<{ name: string; price_adjustment: string }>({
    name: '',
    price_adjustment: '0.00',
  });
  const [variantSubmitting, setVariantSubmitting] = useState<boolean>(false);
  const [variantError, setVariantError] = useState<string | null>(null);

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

  // Product Modal Actions
  const openCreateProductModal = () => {
    setEditingProduct(null);
    setProductForm({
      name: '',
      type: 'service',
      sales_price: '',
      cost_price: '',
      notes: '',
    });
    setProductFormError(null);
    setShowProductModal(true);
  };

  const openEditProductModal = (product: ProductApiItem) => {
    setEditingProduct(product);
    setProductForm({
      name: product.name,
      type: product.type,
      sales_price: String(product.sales_price),
      cost_price: product.cost_price !== null && product.cost_price !== undefined ? String(product.cost_price) : '',
      notes: product.notes || '',
    });
    setProductFormError(null);
    setShowProductModal(true);
  };

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setProductFormError(null);

    const salesPrice = parseFloat(productForm.sales_price);
    const costPrice = parseFloat(productForm.cost_price);

    if (isNaN(salesPrice) || salesPrice < 0) {
      setProductFormError('Sales price must be a valid non-negative number.');
      return;
    }
    if (isNaN(costPrice) || costPrice < 0) {
      setProductFormError('Cost price must be a valid non-negative number.');
      return;
    }

    setProductSubmitting(true);
    try {
      if (editingProduct) {
        const payload: UpdateProductPayload = {
          name: productForm.name.trim(),
          type: productForm.type,
          sales_price: productForm.sales_price,
          cost_price: productForm.cost_price,
          notes: productForm.notes.trim() || undefined,
        };
        await api.updateProduct(editingProduct.id, payload);
        setFeedback({ type: 'success', message: `Product "${productForm.name}" updated successfully.` });
      } else {
        const payload: CreateProductPayload = {
          name: productForm.name.trim(),
          type: productForm.type,
          sales_price: productForm.sales_price,
          cost_price: productForm.cost_price,
          notes: productForm.notes.trim() || undefined,
        };
        await api.createProduct(payload);
        setFeedback({ type: 'success', message: `Product "${productForm.name}" created successfully.` });
      }

      setShowProductModal(false);
      fetchProducts();
    } catch (err) {
      setProductFormError(err instanceof Error ? err.message : 'Failed to save product.');
    } finally {
      setProductSubmitting(false);
    }
  };

  const handleArchiveProduct = async (product: ProductApiItem) => {
    if (!window.confirm(`Archive product "${product.name}"? It will no longer be available for new subscriptions.`)) {
      return;
    }
    try {
      await api.archiveProduct(product.id);
      setFeedback({ type: 'success', message: `Product "${product.name}" archived successfully.` });
      fetchProducts();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to archive product.' });
    }
  };

  // Variants Modal Actions
  const openVariantsModal = async (product: ProductApiItem) => {
    setSelectedProductForVariants(product);
    setVariantForm({ name: '', price_adjustment: '0.00' });
    setVariantError(null);
    setVariantLoading(true);

    try {
      const vars = await api.getProductVariants(product.id);
      setVariantList(vars);
    } catch (err) {
      setVariantError(err instanceof Error ? err.message : 'Failed to load product variants.');
    } finally {
      setVariantLoading(false);
    }
  };

  const handleAddVariant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProductForVariants) return;
    setVariantError(null);

    const adj = parseFloat(variantForm.price_adjustment);
    if (isNaN(adj)) {
      setVariantError('Price adjustment must be a valid number.');
      return;
    }

    setVariantSubmitting(true);
    try {
      await api.createProductVariant(selectedProductForVariants.id, {
        name: variantForm.name.trim(),
        price_adjustment: variantForm.price_adjustment,
      });

      const updated = await api.getProductVariants(selectedProductForVariants.id);
      setVariantList(updated);
      setVariantForm({ name: '', price_adjustment: '0.00' });
      setFeedback({
        type: 'success',
        message: `Variant "${variantForm.name}" (+${variantForm.price_adjustment}) added.`,
      });
      fetchProducts();
    } catch (err) {
      setVariantError(err instanceof Error ? err.message : 'Failed to add variant.');
    } finally {
      setVariantSubmitting(false);
    }
  };

  const handleArchiveVariant = async (variant: ProductVariantApiItem) => {
    if (!selectedProductForVariants) return;
    try {
      await api.archiveProductVariant(selectedProductForVariants.id, variant.id);
      const updated = await api.getProductVariants(selectedProductForVariants.id);
      setVariantList(updated);
      fetchProducts();
      setFeedback({ type: 'success', message: `Variant "${variant.name}" archived.` });
    } catch (err) {
      setVariantError(err instanceof Error ? err.message : 'Failed to archive variant.');
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Products & Variants Catalog"
        subtitle={
          isAdmin
            ? 'Configure products, pricing, and brand variants with exact price adjustments (e.g. Odoo brand adds +$560).'
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
              <button
                onClick={openCreateProductModal}
                className="px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-xs sm:text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-1.5 shadow-xs"
              >
                <Plus className="w-4 h-4" />
                <span>Add Product</span>
              </button>
            )}
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

      {error && <ErrorState message={error} onRetry={fetchProducts} />}

      <SearchAndFilterBar
        searchQuery={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          setPage(1);
        }}
        searchPlaceholder="Search products by name or notes..."
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
              <table className="w-full text-left border-collapse text-sm min-w-[750px]">
                <thead>
                  <tr className="bg-slate-50 text-slate-600 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                    <th className="py-3 px-4">Product Name</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Variants & Price Adjustments</th>
                    <th className="py-3 px-4 text-right">Sales Price</th>
                    <th className="py-3 px-4 text-right">Cost Price</th>
                    {isAdmin && <th className="py-3 px-4 text-center">Actions</th>}
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
                        <div className="flex flex-wrap items-center gap-1.5">
                          {p.variants && p.variants.length > 0 ? (
                            p.variants.map((v, idx) => (
                              <span
                                key={idx}
                                className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100"
                              >
                                <Tag className="w-3 h-3 text-indigo-500" />
                                {v.name}
                                <span className="font-semibold text-indigo-900">
                                  (+${Number(v.price_adjustment).toFixed(2)})
                                </span>
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-slate-400">No variants</span>
                          )}
                          {isAdmin && (
                            <button
                              onClick={() => openVariantsModal(p)}
                              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 underline decoration-dotted ml-1"
                            >
                              Manage
                            </button>
                          )}
                        </div>
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
                      {isAdmin && (
                        <td className="py-3.5 px-4 text-center">
                          <div className="flex items-center justify-center gap-2">
                            <button
                              onClick={() => openEditProductModal(p)}
                              className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition"
                              title="Edit product"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleArchiveProduct(p)}
                              className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                              title="Archive product"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      )}
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

      {/* Product Add/Edit Modal */}
      {showProductModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-base">
                  {editingProduct ? 'Edit Product' : 'Add New Product'}
                </h3>
              </div>
              <button
                onClick={() => setShowProductModal(false)}
                className="text-slate-400 hover:text-slate-600 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveProduct} className="p-6 space-y-4">
              {productFormError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                  {productFormError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Product Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Brightloop Core ERP"
                  value={productForm.name}
                  onChange={(e) => setProductForm({ ...productForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Product Type *</label>
                <select
                  value={productForm.type}
                  onChange={(e) => setProductForm({ ...productForm, type: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="service">Service</option>
                  <option value="goods">Goods (Stockable)</option>
                  <option value="consumable">Consumable</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Sales Price ($) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    placeholder="100.00"
                    value={productForm.sales_price}
                    onChange={(e) => setProductForm({ ...productForm, sales_price: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Cost Price ($) * <span className="text-slate-400 font-normal">(Admin Only)</span>
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    placeholder="40.00"
                    value={productForm.cost_price}
                    onChange={(e) => setProductForm({ ...productForm, cost_price: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Notes / Description</label>
                <textarea
                  rows={2}
                  placeholder="Optional internal specifications or customer-visible notes..."
                  value={productForm.notes}
                  onChange={(e) => setProductForm({ ...productForm, notes: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowProductModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={productSubmitting}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {productSubmitting ? 'Saving...' : editingProduct ? 'Update Product' : 'Create Product'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Variants Management Modal */}
      {selectedProductForVariants && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-indigo-600" />
                <div>
                  <h3 className="font-bold text-slate-900 text-base">
                    Brand Variants & Adjustments
                  </h3>
                  <div className="text-xs text-slate-500">{selectedProductForVariants.name}</div>
                </div>
              </div>
              <button
                onClick={() => setSelectedProductForVariants(null)}
                className="text-slate-400 hover:text-slate-600 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {variantError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                  {variantError}
                </div>
              )}

              {/* Add Variant Form */}
              <form onSubmit={handleAddVariant} className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-600">
                  Add Brand or Edition Variant
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Variant Name *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Odoo Brand Edition"
                      value={variantForm.name}
                      onChange={(e) => setVariantForm({ ...variantForm, name: e.target.value })}
                      className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Price Adjustment ($) *
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      placeholder="e.g. 560.00"
                      value={variantForm.price_adjustment}
                      onChange={(e) => setVariantForm({ ...variantForm, price_adjustment: e.target.value })}
                      className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm font-mono bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>
                <div className="flex justify-end pt-1">
                  <button
                    type="submit"
                    disabled={variantSubmitting}
                    className="px-3.5 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700 disabled:opacity-50 transition flex items-center gap-1.5"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>{variantSubmitting ? 'Adding...' : 'Add Variant'}</span>
                  </button>
                </div>
              </form>

              {/* Existing Variants List */}
              <div className="space-y-2">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-600">
                  Active Variants ({variantList.length})
                </div>
                {variantLoading ? (
                  <LoadingState message="Loading variants..." rows={2} />
                ) : variantList.length === 0 ? (
                  <div className="text-center py-6 text-xs text-slate-400 bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
                    No variants configured yet. Use the form above to add an edition or brand (e.g. Odoo brand +$560).
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white">
                    {variantList.map((v) => (
                      <div
                        key={v.id}
                        className="flex items-center justify-between p-3 hover:bg-slate-50 transition text-sm"
                      >
                        <div className="flex items-center gap-2">
                          <Tag className="w-4 h-4 text-indigo-500" />
                          <span className="font-semibold text-slate-900">{v.name}</span>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="font-mono font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded text-xs border border-indigo-100">
                            {Number(v.price_adjustment) >= 0 ? '+' : ''}${Number(v.price_adjustment).toFixed(2)}
                          </span>
                          <button
                            onClick={() => handleArchiveVariant(v)}
                            className="p-1 text-slate-400 hover:text-red-600 rounded transition"
                            title="Archive variant"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex justify-end pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setSelectedProductForVariants(null)}
                  className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg text-sm font-semibold hover:bg-slate-200 transition"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { Lock, Plus, Tag, RefreshCw } from 'lucide-react';

interface ProductItem {
  id: string;
  name: string;
  type: string;
  sales_price: number;
  cost_price?: number | null;
  notes?: string;
  variants: { name: string; price_adjustment: number }[];
}

export const Catalog: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isLive, setIsLive] = useState<boolean>(false);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const data = await api.getProducts();
      setProducts(data);
      setIsLive(true);
    } catch {
      // Fallback
      setProducts([
        {
          id: '1',
          name: 'Brightloop Core ERP',
          type: 'service',
          sales_price: 100.0,
          cost_price: isAdmin ? 30.0 : null,
          variants: [{ name: 'Brand: Odoo', price_adjustment: 560.0 }],
          notes: 'Core ERP subscription module.',
        },
        {
          id: '2',
          name: 'Advanced Analytics Add-on',
          type: 'service',
          sales_price: 45.0,
          cost_price: isAdmin ? 10.0 : null,
          variants: [],
          notes: 'Real-time financial KPI dashboard.',
        },
      ]);
      setIsLive(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, [user?.role]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Products & Variants Catalog</h1>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                isLive ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {isLive ? '● Live API Data' : 'Cached Baseline'}
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            {isAdmin
              ? 'Configure products, pricing, and brand variants (e.g. Odoo brand +560).'
              : 'View product catalog and active selling prices (Cost prices restricted to Admin).'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchProducts}
            className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 transition"
            title="Refresh from API"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          {isAdmin && (
            <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-2 shadow-xs">
              <Plus className="w-4 h-4" />
              Add Product
            </button>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <table className="w-full text-left border-collapse text-sm">
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
                  <div className="text-xs text-slate-500">{p.notes}</div>
                </td>
                <td className="py-3.5 px-4 capitalize">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                    {p.type}
                  </span>
                </td>
                <td className="py-3.5 px-4">
                  {p.variants && p.variants.length > 0 ? (
                    <div className="space-y-1">
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
                    <span className="text-slate-600 font-medium">${Number(p.cost_price).toFixed(2)}</span>
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
    </div>
  );
};

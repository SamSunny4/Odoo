import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Lock, Plus, Tag } from 'lucide-react';

export const Catalog: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user.role === 'admin';

  const products = [
    {
      id: '1',
      name: 'Brightloop Core ERP',
      type: 'Service',
      salesPrice: 100.00,
      costPrice: 30.00,
      variants: [{ name: 'Brand: Odoo', adjustment: 560.00 }],
      notes: 'Core ERP subscription module.',
    },
    {
      id: '2',
      name: 'Advanced Analytics Add-on',
      type: 'Service',
      salesPrice: 45.00,
      costPrice: 10.00,
      variants: [],
      notes: 'Real-time financial KPI dashboard.',
    },
    {
      id: '3',
      name: 'Dedicated Support Package',
      type: 'Service',
      salesPrice: 250.00,
      costPrice: 80.00,
      variants: [],
      notes: '24/7 priority SLA support.',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Products & Variants Catalog</h1>
          <p className="text-sm text-slate-500">
            {isAdmin
              ? 'Configure products, pricing, and brand variants (e.g. Odoo brand +560).'
              : 'View product catalog and active selling prices (Cost prices restricted to Admin).'}
          </p>
        </div>

        {isAdmin && (
          <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition flex items-center gap-2 shadow-xs">
            <Plus className="w-4 h-4" />
            Add New Product
          </button>
        )}
      </div>

      {/* Product Cards Table */}
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
                <td className="py-3.5 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                    {p.type}
                  </span>
                </td>
                <td className="py-3.5 px-4">
                  {p.variants.length > 0 ? (
                    <div className="space-y-1">
                      {p.variants.map((v, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100"
                        >
                          <Tag className="w-3 h-3" />
                          {v.name} (+${v.adjustment.toFixed(2)})
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400">Standard (None)</span>
                  )}
                </td>
                <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900">
                  ${p.salesPrice.toFixed(2)}
                </td>
                <td className="py-3.5 px-4 text-right font-mono">
                  {isAdmin ? (
                    <span className="text-slate-600 font-medium">${p.costPrice.toFixed(2)}</span>
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


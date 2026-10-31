import React, { useState, useEffect, useCallback } from 'react';
import { api, StaffUserItem } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { PageHeader } from '../components/common/PageHeader';
import { SearchAndFilterBar, FilterOption } from '../components/common/SearchAndFilterBar';
import { PaginationControls } from '../components/common/PaginationControls';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { AlertBanner } from '../components/common/AlertBanner';
import {
  UserPlus,
  Shield,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  X,
  KeyRound,
  Mail,
  User as UserIcon,
} from 'lucide-react';

const ROLE_OPTIONS: FilterOption[] = [
  { label: 'Admin', value: 'admin' },
  { label: 'Staff', value: 'staff' },
];

export const StaffAdmin: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [staffList, setStaffList] = useState<StaffUserItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Pagination & Filtering
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [roleFilter, setRoleFilter] = useState<string>('all');

  // Modal State
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    role: 'staff' as 'admin' | 'staff',
    password: '',
    isActive: true,
  });
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchStaff = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getStaff({
        page,
        pageSize,
        search: searchQuery || undefined,
        role: roleFilter !== 'all' ? roleFilter : undefined,
      });
      setStaffList(data.items);
      setTotal(data.total);
      setTotalPages(data.totalPages);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load staff list.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, searchQuery, roleFilter]);

  useEffect(() => {
    fetchStaff();
  }, [fetchStaff]);

  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      await api.createStaff({
        email: formData.email,
        full_name: formData.fullName,
        password: formData.password,
        role: formData.role,
        is_active: formData.isActive,
      });

      setFeedback({
        type: 'success',
        message: `Successfully created staff account for ${formData.fullName} (${formData.email}).`,
      });
      setShowAddModal(false);
      setFormData({
        fullName: '',
        email: '',
        role: 'staff',
        password: '',
        isActive: true,
      });
      await fetchStaff();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create staff member.';
      setFormError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (staff: StaffUserItem) => {
    if (staff.id === currentUser?.id) {
      setFeedback({ type: 'error', message: 'You cannot deactivate your own account.' });
      return;
    }

    const actionText = staff.is_active ? 'deactivate' : 'activate';
    if (!window.confirm(`Are you sure you want to ${actionText} ${staff.full_name}?`)) {
      return;
    }

    try {
      await api.updateStaff(staff.id, { is_active: !staff.is_active });
      setFeedback({ type: 'success', message: `Updated status for ${staff.full_name}.` });
      await fetchStaff();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update user status.';
      setFeedback({ type: 'error', message });
    }
  };

  const handleRoleToggle = async (staff: StaffUserItem) => {
    if (staff.id === currentUser?.id) {
      setFeedback({ type: 'error', message: 'You cannot alter your own administrative role.' });
      return;
    }

    const newRole: 'admin' | 'staff' = staff.role === 'admin' ? 'staff' : 'admin';
    if (!window.confirm(`Change role of ${staff.full_name} to ${newRole.toUpperCase()}?`)) {
      return;
    }

    try {
      await api.updateStaff(staff.id, { role: newRole });
      setFeedback({ type: 'success', message: `Changed role for ${staff.full_name} to ${newRole}.` });
      await fetchStaff();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update role.';
      setFeedback({ type: 'error', message });
    }
  };

  // Password validation checks
  const pass = formData.password;
  const isLenValid = pass.length > 8;
  const hasUpper = /[A-Z]/.test(pass);
  const hasLower = /[a-z]/.test(pass);
  const hasSpecial = /[\W_]/.test(pass);
  const isPasswordValid = isLenValid && hasUpper && hasLower && hasSpecial;

  const totalAdmins = staffList.filter((s) => s.role === 'admin').length;
  const totalStaff = staffList.filter((s) => s.role === 'staff').length;
  const totalActive = staffList.filter((s) => s.is_active).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Staff & Access Management"
        subtitle="Manage authorized staff members, role boundaries, and operational privileges."
        breadcrumbs={[
          { label: 'Brightloop' },
          { label: 'Catalog & Configuration' },
          { label: 'Staff & Access' },
        ]}
        actions={
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-2 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs sm:text-sm font-semibold shadow-xs transition"
          >
            <UserPlus className="w-4 h-4" />
            <span>Add Staff Member</span>
          </button>
        }
      />

      {feedback && (
        <AlertBanner
          type={feedback.type}
          message={feedback.message}
          onClose={() => setFeedback(null)}
        />
      )}

      {error && <ErrorState message={error} onRetry={fetchStaff} />}

      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Team</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{total}</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Administrators</div>
          <div className="text-2xl font-bold text-indigo-700 mt-1">{totalAdmins}</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Operations Staff</div>
          <div className="text-2xl font-bold text-slate-800 mt-1">{totalStaff}</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Active Users</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{totalActive}</div>
        </div>
      </div>

      <SearchAndFilterBar
        searchQuery={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          setPage(1);
        }}
        searchPlaceholder="Search staff by name or email..."
        statusFilter={roleFilter}
        onStatusChange={(r) => {
          setRoleFilter(r);
          setPage(1);
        }}
        statusOptions={ROLE_OPTIONS}
        onReset={() => {
          setSearchQuery('');
          setRoleFilter('all');
          setPage(1);
        }}
      />

      {/* Staff Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <LoadingState message="Loading staff directory..." rows={4} />
        ) : staffList.length === 0 ? (
          <EmptyState
            title="No staff accounts found"
            description="There are no staff members matching your search or filters."
            action={{
              label: 'Clear Filters',
              onClick: () => {
                setSearchQuery('');
                setRoleFilter('all');
                setPage(1);
              },
            }}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm min-w-[650px]">
                <thead>
                  <tr className="bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-200">
                    <th className="px-6 py-3">Member</th>
                    <th className="px-6 py-3">Email</th>
                    <th className="px-6 py-3">Role</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3">Joined Date</th>
                    <th className="px-6 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {staffList.map((staff) => (
                    <tr key={staff.id} className="hover:bg-slate-50/60 transition">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900 flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center font-bold text-xs">
                            {staff.full_name
                              .split(' ')
                              .map((n) => n[0])
                              .slice(0, 2)
                              .join('')
                              .toUpperCase()}
                          </div>
                          <div>
                            <div>{staff.full_name}</div>
                            {staff.id === currentUser?.id && (
                              <span className="text-[10px] text-indigo-600 font-medium">
                                (Current User)
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-slate-600 font-mono text-xs">{staff.email}</td>
                      <td className="px-6 py-4">
                        {staff.role === 'admin' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                            <Shield className="w-3 h-3" />
                            Admin
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            <ShieldCheck className="w-3 h-3" />
                            Staff
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {staff.is_active ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700">
                            <CheckCircle2 className="w-3 h-3" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-rose-50 text-rose-700">
                            <XCircle className="w-3 h-3" />
                            Inactive
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-slate-500 text-xs">
                        {new Date(staff.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right space-x-2">
                        <button
                          onClick={() => handleRoleToggle(staff)}
                          disabled={staff.id === currentUser?.id}
                          className="text-xs font-medium text-slate-600 hover:text-indigo-600 disabled:opacity-40 disabled:hover:text-slate-600 transition"
                        >
                          Change to {staff.role === 'admin' ? 'Staff' : 'Admin'}
                        </button>
                        <button
                          onClick={() => handleToggleStatus(staff)}
                          disabled={staff.id === currentUser?.id}
                          className={`text-xs font-medium ${
                            staff.is_active
                              ? 'text-rose-600 hover:text-rose-700'
                              : 'text-emerald-600 hover:text-emerald-700'
                          } disabled:opacity-40 transition`}
                        >
                          {staff.is_active ? 'Deactivate' : 'Activate'}
                        </button>
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

      {/* Modal for adding staff */}
      {showAddModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs"
        >
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 max-w-lg w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-indigo-600" />
                Add Operational Staff Member
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateStaff} className="p-6 space-y-4">
              {formError && (
                <AlertBanner
                  type="error"
                  message={formError}
                  onClose={() => setFormError(null)}
                />
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name</label>
                <div className="relative">
                  <UserIcon className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    value={formData.fullName}
                    onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                    placeholder="e.g. Jane Doe"
                    className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="jane@brightloop.local"
                    className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Role Boundary</label>
                  <select
                    value={formData.role}
                    onChange={(e) =>
                      setFormData({ ...formData, role: e.target.value as 'admin' | 'staff' })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 bg-white"
                  >
                    <option value="staff">Staff (Operational)</option>
                    <option value="admin">Administrator (Full Access)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Initial Status</label>
                  <select
                    value={formData.isActive ? 'active' : 'inactive'}
                    onChange={(e) =>
                      setFormData({ ...formData, isActive: e.target.value === 'active' })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 bg-white"
                  >
                    <option value="active">Active (Can Login)</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Temporary Password
                </label>
                <div className="relative">
                  <KeyRound className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="password"
                    required
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="Must meet complexity rules"
                    className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>

                <div className="mt-2 text-[11px] grid grid-cols-2 gap-1 text-slate-500">
                  <span className={isLenValid ? 'text-emerald-600 font-medium' : ''}>
                    • &gt; 8 characters
                  </span>
                  <span className={hasUpper ? 'text-emerald-600 font-medium' : ''}>
                    • 1 uppercase letter
                  </span>
                  <span className={hasLower ? 'text-emerald-600 font-medium' : ''}>
                    • 1 lowercase letter
                  </span>
                  <span className={hasSpecial ? 'text-emerald-600 font-medium' : ''}>
                    • 1 special symbol
                  </span>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !isPasswordValid}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs transition"
                >
                  {submitting ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

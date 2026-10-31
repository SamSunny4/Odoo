import React, { useState, useEffect } from 'react';
import { api, StaffUserItem } from '../services/api';
import { useAuth } from '../context/AuthContext';
import {
  Users,
  UserPlus,
  Shield,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertCircle,
  X,
  KeyRound,
  Mail,
  User as UserIcon,
} from 'lucide-react';

export const StaffAdmin: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [staffList, setStaffList] = useState<StaffUserItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

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

  const fetchStaff = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getStaff();
      setStaffList(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load staff list.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStaff();
  }, []);

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

      setSuccessMessage(`Successfully created staff account for ${formData.fullName} (${formData.email}).`);
      setShowAddModal(false);
      setFormData({
        fullName: '',
        email: '',
        role: 'staff',
        password: '',
        isActive: true,
      });
      fetchStaff();
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create staff member.';
      setFormError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (staff: StaffUserItem) => {
    if (staff.id === currentUser?.id) {
      alert('You cannot deactivate your own account.');
      return;
    }

    const actionText = staff.is_active ? 'deactivate' : 'activate';
    if (!window.confirm(`Are you sure you want to ${actionText} ${staff.full_name}?`)) {
      return;
    }

    try {
      await api.updateStaff(staff.id, { is_active: !staff.is_active });
      setSuccessMessage(`Updated status for ${staff.full_name}.`);
      fetchStaff();
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update user status.';
      setError(message);
    }
  };

  const handleRoleToggle = async (staff: StaffUserItem) => {
    if (staff.id === currentUser?.id) {
      alert('You cannot alter your own administrative role.');
      return;
    }

    const newRole: 'admin' | 'staff' = staff.role === 'admin' ? 'staff' : 'admin';
    if (!window.confirm(`Change role of ${staff.full_name} to ${newRole.toUpperCase()}?`)) {
      return;
    }

    try {
      await api.updateStaff(staff.id, { role: newRole });
      setSuccessMessage(`Changed role for ${staff.full_name} to ${newRole}.`);
      fetchStaff();
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update role.';
      setError(message);
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
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Users className="w-6 h-6 text-indigo-600" />
            Staff & Access Management
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage authorized staff members, role boundaries, and operational privileges.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow-sm transition"
        >
          <UserPlus className="w-4 h-4" />
          Add Staff Member
        </button>
      </div>

      {/* Alerts */}
      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Team</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{staffList.length}</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Administrators</div>
          <div className="text-2xl font-bold text-indigo-700 mt-1">{totalAdmins}</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Operations Staff</div>
          <div className="text-2xl font-bold text-slate-800 mt-1">{totalStaff}</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Active Users</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{totalActive}</div>
        </div>
      </div>

      {/* Staff Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">Organization Staff Directory</h2>
          <span className="text-xs text-slate-500">
            Authorization strictly verified by the API on every mutation
          </span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-slate-400">Loading staff directory...</div>
        ) : staffList.length === 0 ? (
          <div className="p-12 text-center text-sm text-slate-500">No staff accounts found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
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
              <tbody className="divide-y divide-slate-100 text-sm">
                {staffList.map((staff) => (
                  <tr key={staff.id} className="hover:bg-slate-50 transition">
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
                            <span className="text-[10px] text-indigo-600 font-medium">(Current User)</span>
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
        )}
      </div>

      {/* Add Staff Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900">Add New Staff Member</h3>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateStaff} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <UserIcon className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. Jordan Smith"
                    value={formData.fullName}
                    onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                    className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Work Email Address
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="email"
                    required
                    placeholder="staff@brightloop.local"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Access Role
                </label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value as 'admin' | 'staff' })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="staff">Operations Staff (Day-to-day operations & quotes)</option>
                  <option value="admin">Administrator (Full configuration & user access)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Temporary Password
                </label>
                <div className="relative">
                  <KeyRound className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="password"
                    required
                    placeholder="Min 9 chars with Upper, Lower & Symbol"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                {/* Password policy checklist */}
                <div className="mt-2 p-2.5 bg-slate-50 border border-slate-200 rounded-lg space-y-1 text-xs">
                  <div className="font-semibold text-slate-600 mb-1">Brightloop Password Complexity Requirements:</div>
                  <div className={`flex items-center gap-1.5 ${isLenValid ? 'text-emerald-700' : 'text-slate-400'}`}>
                    {isLenValid ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                    <span>More than 8 characters long ({pass.length} / 9+)</span>
                  </div>
                  <div className={`flex items-center gap-1.5 ${hasUpper ? 'text-emerald-700' : 'text-slate-400'}`}>
                    {hasUpper ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                    <span>At least 1 uppercase letter (A-Z)</span>
                  </div>
                  <div className={`flex items-center gap-1.5 ${hasLower ? 'text-emerald-700' : 'text-slate-400'}`}>
                    {hasLower ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                    <span>At least 1 lowercase letter (a-z)</span>
                  </div>
                  <div className={`flex items-center gap-1.5 ${hasSpecial ? 'text-emerald-700' : 'text-slate-400'}`}>
                    {hasSpecial ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                    <span>At least 1 special character (@, #, $, !, etc.)</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="isActiveCheck"
                  checked={formData.isActive}
                  onChange={(e) => setFormData({ ...formData, isActive: e.target.checked })}
                  className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <label htmlFor="isActiveCheck" className="text-xs text-slate-700 font-medium">
                  Active immediately upon creation
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !isPasswordValid}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow-sm transition disabled:opacity-50"
                >
                  {submitting ? 'Creating...' : 'Create Staff Member'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};


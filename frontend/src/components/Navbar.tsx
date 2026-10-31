import React from 'react';
import { useAuth } from '../context/AuthContext';
import { ShieldCheck, UserCheck, Building2, LogOut } from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, switchRole, logout } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200 sticky top-0 z-30 px-4 sm:px-6 flex items-center justify-between">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-sm">
          B
        </div>
        <div>
          <span className="font-semibold text-slate-900 tracking-tight text-base sm:text-lg">Brightloop</span>
          <span className="text-xs text-slate-500 block leading-none">Subscription OS</span>
        </div>
      </div>

      {/* Role Switcher & User Profile */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Quick Role Simulator Switcher */}
        <div className="flex items-center bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs font-medium">
          <span className="text-slate-500 px-2 hidden md:inline">Simulate Role:</span>
          <button
            onClick={() => switchRole('admin')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition ${
              user?.role === 'admin'
                ? 'bg-indigo-600 text-white shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            Admin
          </button>
          <button
            onClick={() => switchRole('staff')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition ${
              user?.role === 'staff'
                ? 'bg-emerald-600 text-white shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <UserCheck className="w-3.5 h-3.5" />
            Staff
          </button>
          <button
            onClick={() => switchRole('customer')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition ${
              user?.role === 'customer'
                ? 'bg-blue-600 text-white shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            Customer
          </button>
        </div>

        {/* User Pill & Logout */}
        <div className="flex items-center gap-3 border-l border-slate-200 pl-3">
          <div className="text-right hidden sm:block">
            <div className="text-xs font-semibold text-slate-800">{user?.fullName || 'User'}</div>
            <div className="text-[11px] text-slate-500 capitalize">{user?.role} {user?.companyName ? `• ${user.companyName}` : ''}</div>
          </div>
          <div className="h-8 w-8 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center text-xs font-semibold text-slate-700">
            {user?.fullName?.charAt(0) || 'U'}
          </div>
          <button
            onClick={logout}
            title="Log Out"
            className="p-1.5 text-slate-400 hover:text-red-600 rounded-md transition"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};

import React from 'react';
import { useAuth } from '../context/AuthContext';
import { ShieldCheck, UserCheck, Building2, LogOut, Menu } from 'lucide-react';

interface NavbarProps {
  onToggleMobileMenu?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onToggleMobileMenu }) => {
  const { user, switchRole, logout } = useAuth();

  return (
    <header className="h-16 bg-white/95 backdrop-blur-md border-b border-sky-100 sticky top-0 z-30 px-3 sm:px-6 flex items-center justify-between relative shadow-xs">
      {/* Top radiant hairline */}
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-sky-400 via-yellow-400 to-sky-500" />

      {/* Brand & Mobile Hamburger */}
      <div className="flex items-center gap-2.5 sm:gap-3">
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            aria-label="Open navigation menu"
            className="md:hidden p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-sky-50 transition focus:outline-none focus:ring-2 focus:ring-sky-500/20"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <div className="relative h-9 w-9 bg-gradient-to-br from-sky-500 to-sky-600 rounded-xl flex items-center justify-center text-white font-black text-lg shadow-sm shadow-sky-500/30 flex-shrink-0 ring-2 ring-yellow-400/90">
          <span>B</span>
          <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-yellow-400 rounded-full border-2 border-white shadow-xs" />
        </div>
        <div>
          <span className="font-bold text-slate-900 tracking-tight text-base sm:text-lg">Brightloop</span>
          <span className="text-[11px] text-sky-600 font-semibold block leading-none">Subscription OS</span>
        </div>
      </div>

      {/* Role Switcher & User Profile */}
      <div className="flex items-center gap-2 sm:gap-4">
        {/* Quick Role Simulator Switcher */}
        <div className="flex items-center bg-slate-100 p-0.5 sm:p-1 rounded-lg border border-slate-200 text-xs font-medium">
          <span className="text-slate-500 px-2 hidden lg:inline">Simulate Role:</span>
          <button
            onClick={() => switchRole('admin')}
            aria-label="Switch to Admin role"
            className={`flex items-center gap-1 px-2 sm:px-2.5 py-1 rounded-md transition ${
              user?.role === 'admin'
                ? 'bg-indigo-600 text-white shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Admin</span>
          </button>
          <button
            onClick={() => switchRole('staff')}
            aria-label="Switch to Staff role"
            className={`flex items-center gap-1 px-2 sm:px-2.5 py-1 rounded-md transition ${
              user?.role === 'staff'
                ? 'bg-emerald-600 text-white shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <UserCheck className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Staff</span>
          </button>
          <button
            onClick={() => switchRole('customer')}
            aria-label="Switch to Customer role"
            className={`flex items-center gap-1 px-2 sm:px-2.5 py-1 rounded-md transition ${
              user?.role === 'customer'
                ? 'bg-blue-600 text-white shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Customer</span>
          </button>
        </div>

        {/* User Pill & Logout */}
        <div className="flex items-center gap-2 sm:gap-3 border-l border-slate-200 pl-2 sm:pl-3">
          <div className="text-right hidden sm:block">
            <div className="text-xs font-semibold text-slate-800">{user?.fullName || 'User'}</div>
            <div className="text-[11px] text-slate-500 capitalize">
              {user?.role} {user?.companyName ? `• ${user.companyName}` : ''}
            </div>
          </div>
          <div className="relative">
            <div
              title={user?.fullName || 'User'}
              className="h-8 w-8 rounded-full bg-sky-100 border border-sky-300 flex items-center justify-center text-xs font-bold text-sky-800 shadow-2xs"
            >
              {user?.fullName?.charAt(0) || 'U'}
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-yellow-400 ring-2 ring-white" />
          </div>
          <button
            onClick={logout}
            title="Log Out"
            aria-label="Log out"
            className="p-1.5 text-slate-400 hover:text-red-600 rounded-md transition"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};

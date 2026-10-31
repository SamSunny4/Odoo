import React, { useState, useEffect } from 'react';
import { useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { MobileDrawer } from './components/common/MobileDrawer';
import { Dashboard } from './pages/Dashboard';
import { ControlTower } from './pages/ControlTower';
import { Catalog } from './pages/Catalog';
import { Subscriptions } from './pages/Subscriptions';
import { Invoices } from './pages/Invoices';
import { CustomerPortal } from './pages/CustomerPortal';
import { Login } from './pages/Login';
import { StaffAdmin } from './pages/StaffAdmin';
import { PlansAdmin } from './pages/PlansAdmin';
import { DiscountsAdmin } from './pages/DiscountsAdmin';
import { ShieldAlert } from 'lucide-react';

export const AppContent: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [isMobileNavOpen, setIsMobileNavOpen] = useState<boolean>(false);

  useEffect(() => {
    if (user?.role === 'customer') {
      if (!currentTab.startsWith('portal-')) {
        setCurrentTab('portal-subscriptions');
      }
    } else {
      if (currentTab.startsWith('portal-')) {
        setCurrentTab('dashboard');
      }
    }
  }, [user?.role]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center text-slate-500 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <span>Restoring session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Login />;
  }

  const navigateFromBreadcrumb = (tabKey: string) => {
    if (user.role === 'customer') {
      setCurrentTab(tabKey.startsWith('portal-') ? tabKey : 'portal-subscriptions');
      return;
    }
    if (user.role === 'staff' && ['plans', 'discounts', 'team'].includes(tabKey)) {
      return;
    }
    setCurrentTab(tabKey);
  };

  const renderContent = () => {
    if (user.role === 'customer') {
      return <CustomerPortal activeTab={currentTab} onNavigate={navigateFromBreadcrumb} />;
    }

    // Role-based route guard for staff vs admin
    const adminOnlyTabs = ['plans', 'discounts', 'team'];
    if (user.role === 'staff' && adminOnlyTabs.includes(currentTab)) {
      return (
        <div role="alert" className="bg-white rounded-xl border border-red-200 p-8 text-center space-y-4 max-w-lg mx-auto mt-12 shadow-xs">
          <div className="h-12 w-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">Access Restricted</h2>
          <p className="text-sm text-slate-600">
            This administrative module requires Administrator privileges. Your account currently holds the <span className="font-semibold text-emerald-700">Staff</span> role.
          </p>
          <button
            onClick={() => setCurrentTab('dashboard')}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition"
          >
            Return to Operations Queue
          </button>
        </div>
      );
    }

    switch (currentTab) {
      case 'dashboard':
        return <Dashboard onNavigate={navigateFromBreadcrumb} />;
      case 'control-tower':
        return <ControlTower onNavigate={navigateFromBreadcrumb} />;
      case 'catalog':
        return <Catalog onNavigate={navigateFromBreadcrumb} />;
      case 'subscriptions':
        return <Subscriptions onNavigate={navigateFromBreadcrumb} />;
      case 'invoices':
        return <Invoices onNavigate={navigateFromBreadcrumb} />;
      case 'team':
        return <StaffAdmin onNavigate={navigateFromBreadcrumb} />;
      case 'plans':
        return <PlansAdmin onNavigate={navigateFromBreadcrumb} />;
      case 'discounts':
        return <DiscountsAdmin onNavigate={navigateFromBreadcrumb} />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-slate-900 font-sans">
      <Navbar onToggleMobileMenu={() => setIsMobileNavOpen(true)} />
      <MobileDrawer
        isOpen={isMobileNavOpen}
        onClose={() => setIsMobileNavOpen(false)}
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
      />
      <div className="flex-1 flex flex-col md:flex-row">
        <Sidebar currentTab={currentTab} onSelectTab={setCurrentTab} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default function App() {
  return <AppContent />;
}

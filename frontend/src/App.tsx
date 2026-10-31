import React, { useState, useEffect } from 'react';
import { useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { ControlTower } from './pages/ControlTower';
import { Catalog } from './pages/Catalog';
import { Subscriptions } from './pages/Subscriptions';
import { Invoices } from './pages/Invoices';
import { CustomerPortal } from './pages/CustomerPortal';
import { Login } from './pages/Login';
import { StaffAdmin } from './pages/StaffAdmin';

export const AppContent: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [currentTab, setCurrentTab] = useState<string>('dashboard');

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
        Restoring session...
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Login />;
  }

  const renderContent = () => {
    if (user.role === 'customer') {
      return <CustomerPortal activeTab={currentTab} />;
    }

    switch (currentTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'control-tower':
        return <ControlTower />;
      case 'catalog':
        return <Catalog />;
      case 'subscriptions':
        return <Subscriptions />;
      case 'invoices':
        return <Invoices />;
      case 'team':
        return <StaffAdmin />;
      case 'plans':
      case 'discounts':
        return (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center space-y-3">
            <h2 className="text-xl font-bold text-slate-800 capitalize">{currentTab} Administration</h2>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              This module is scheduled for implementation in Phase 1 & Phase 3. The underlying domain models ({currentTab}) have been fully scaffolded in Phase 0.
            </p>
          </div>
        );
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-slate-900 font-sans">
      <Navbar />
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

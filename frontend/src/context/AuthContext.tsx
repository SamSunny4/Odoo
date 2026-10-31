import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

export type UserRole = 'admin' | 'staff' | 'customer';

export interface User {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  companyName?: string;
}

interface AuthContextType {
  user: User;
  switchRole: (role: UserRole) => Promise<void>;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const SEEDED_CREDENTIALS: Record<UserRole, { email: string; pass: string; user: User }> = {
  admin: {
    email: 'admin@brightloop.local',
    pass: 'Admin@12345!',
    user: {
      id: '11111111-1111-1111-1111-111111111111',
      email: 'admin@brightloop.local',
      fullName: 'Brightloop Administrator',
      role: 'admin',
    },
  },
  staff: {
    email: 'staff@brightloop.local',
    pass: 'Staff@12345!',
    user: {
      id: '22222222-2222-2222-2222-222222222222',
      email: 'staff@brightloop.local',
      fullName: 'Operations Staff',
      role: 'staff',
    },
  },
  customer: {
    email: 'customer@acme.com',
    pass: 'Customer@12345!',
    user: {
      id: '33333333-3333-3333-3333-333333333333',
      email: 'customer@acme.com',
      fullName: 'Alex Mercer',
      role: 'customer',
      companyName: 'Acme Corporation',
    },
  },
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentRole, setCurrentRole] = useState<UserRole>(() => {
    const saved = localStorage.getItem('brightloop_active_role');
    return (saved as UserRole) || 'admin';
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [currentUser, setCurrentUser] = useState<User>(SEEDED_CREDENTIALS[currentRole].user);

  const switchRole = async (role: UserRole) => {
    setIsLoading(true);
    setCurrentRole(role);
    localStorage.setItem('brightloop_active_role', role);

    const cred = SEEDED_CREDENTIALS[role];
    try {
      // Authenticate against real backend API
      await api.login(cred.email, cred.pass);
      const meData = await api.getMe();
      setCurrentUser({
        id: meData.user.id,
        email: meData.user.email,
        fullName: meData.user.full_name,
        role: meData.user.role as UserRole,
        companyName: meData.customer_account?.company_name,
      });
    } catch {
      // Graceful fallback for offline / mock dev mode
      setCurrentUser(cred.user);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    switchRole(currentRole);
  }, []);

  return (
    <AuthContext.Provider value={{ user: currentUser, switchRole, isAuthenticated: true, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

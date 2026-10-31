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
  user: User | null;
  login: (email: string, pass: string) => Promise<void>;
  signup: (data: any) => Promise<void>;
  logout: () => void;
  switchRole: (role: UserRole) => Promise<void>;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const SEEDED_CREDENTIALS: Record<UserRole, { email: string; pass: string }> = {
  admin: {
    email: 'admin@brightloop.local',
    pass: 'Admin@12345!',
  },
  staff: {
    email: 'staff@brightloop.local',
    pass: 'Staff@12345!',
  },
  customer: {
    email: 'customer@acme.com',
    pass: 'Customer@12345!',
  },
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return !!localStorage.getItem('brightloop_jwt_token');
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Restore session from token
  const restoreSession = async () => {
    const token = localStorage.getItem('brightloop_jwt_token');
    if (!token) {
      setIsAuthenticated(false);
      setIsLoading(false);
      return;
    }

    try {
      const meData = await api.getMe();
      setCurrentUser({
        id: meData.user.id,
        email: meData.user.email,
        fullName: meData.user.full_name,
        role: meData.user.role as UserRole,
        companyName: meData.customer_account?.company_name,
      });
      setIsAuthenticated(true);
    } catch {
      // Token expired or invalid
      localStorage.removeItem('brightloop_jwt_token');
      setIsAuthenticated(false);
      setCurrentUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    restoreSession();
  }, []);

  const login = async (email: string, pass: string) => {
    setIsLoading(true);
    try {
      await api.login(email, pass);
      const meData = await api.getMe();
      setCurrentUser({
        id: meData.user.id,
        email: meData.user.email,
        fullName: meData.user.full_name,
        role: meData.user.role as UserRole,
        companyName: meData.customer_account?.company_name,
      });
      setIsAuthenticated(true);
    } finally {
      setIsLoading(false);
    }
  };

  const signup = async (data: any) => {
    setIsLoading(true);
    try {
      const resp = await fetch('http://localhost:8000/api/v1/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Signup failed');
      }
      const tokenData = await resp.json();
      localStorage.setItem('brightloop_jwt_token', tokenData.access_token);
      await restoreSession();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('brightloop_jwt_token');
    setCurrentUser(null);
    setIsAuthenticated(false);
  };

  const switchRole = async (role: UserRole) => {
    const cred = SEEDED_CREDENTIALS[role];
    try {
      await login(cred.email, cred.pass);
    } catch {
      // Fallback for offline dev
      setCurrentUser({
        id: '00000000-0000-0000-0000-000000000000',
        email: cred.email,
        fullName: `${role.toUpperCase()} User`,
        role,
      });
      setIsAuthenticated(true);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user: currentUser,
        login,
        signup,
        logout,
        switchRole,
        isAuthenticated,
        isLoading,
      }}
    >
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

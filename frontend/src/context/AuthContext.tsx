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
  signup: (data: Record<string, unknown>) => Promise<void>;
  logout: () => void | Promise<void>;
  switchRole: (role: UserRole) => Promise<void>;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Restore session from HTTP-only cookie or cached credential
  const restoreSession = async () => {
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
      // Session absent or expired
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
    } catch (error) {
      localStorage.removeItem('brightloop_jwt_token');
      setCurrentUser(null);
      setIsAuthenticated(false);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const signup = async (data: Record<string, unknown>) => {
    setIsLoading(true);
    try {
      const tokenData = await api.signup(data);
      localStorage.setItem('brightloop_jwt_token', tokenData.access_token);
      await restoreSession();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Ignore network errors
    }
    localStorage.removeItem('brightloop_jwt_token');
    setCurrentUser(null);
    setIsAuthenticated(false);
  };

  const switchRole = async (role: UserRole) => {
    try {
      await login(
        role === 'admin' ? 'admin@brightloop.local' : role === 'staff' ? 'staff@brightloop.local' : 'customer@acme.com',
        role === 'admin' ? 'Admin@12345!' : role === 'staff' ? 'Staff@12345!' : 'Customer@12345!',
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to sign in with that demo account.';
      window.alert(message);
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

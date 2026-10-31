import React, { createContext, useContext, useState } from 'react';

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
  switchRole: (role: UserRole) => void;
  isAuthenticated: boolean;
}

const DEFAULT_USERS: Record<UserRole, User> = {
  admin: {
    id: '11111111-1111-1111-1111-111111111111',
    email: 'admin@brightloop.local',
    fullName: 'Brightloop Administrator',
    role: 'admin',
  },
  staff: {
    id: '22222222-2222-2222-2222-222222222222',
    email: 'staff@brightloop.local',
    fullName: 'Operations Staff',
    role: 'staff',
  },
  customer: {
    id: '33333333-3333-3333-3333-333333333333',
    email: 'alex@acme.com',
    fullName: 'Alex Mercer',
    role: 'customer',
    companyName: 'Acme Corporation',
  },
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentRole, setCurrentRole] = useState<UserRole>(() => {
    const saved = localStorage.getItem('brightloop_active_role');
    return (saved as UserRole) || 'admin';
  });

  const switchRole = (role: UserRole) => {
    setCurrentRole(role);
    localStorage.setItem('brightloop_active_role', role);
  };

  const user = DEFAULT_USERS[currentRole];

  return (
    <AuthContext.Provider value={{ user, switchRole, isAuthenticated: true }}>
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


const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/v1';

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('brightloop_jwt_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = {
    'Content-Type': 'application/json',
    ...getAuthHeader(),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorBody.detail || `HTTP Error ${response.status}`);
  }

  return response.json();
}

export const api = {
  // Auth
  login: async (email: string, password: string) => {
    const data = await request<{ access_token: string; token_type: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem('brightloop_jwt_token', data.access_token);
    return data;
  },

  getMe: () => request<any>('/auth/me'),

  // Catalog
  getProducts: () => request<any[]>('/products'),
  getPlans: () => request<any[]>('/plans'),

  // Subscriptions
  getSubscriptions: () => request<any[]>('/subscriptions'),
  pauseSubscription: (id: string) =>
    request<any>(`/subscriptions/${id}/pause`, { method: 'POST' }),
  resumeSubscription: (id: string) =>
    request<any>(`/subscriptions/${id}/resume`, { method: 'POST' }),

  // Invoices & Payments
  getInvoices: () => request<any[]>('/invoices'),
  recordPayment: (payload: {
    invoice_id: string;
    amount: number;
    payment_method: string;
    payment_date: string;
    reference_note?: string;
  }) => request<any>('/payments', { method: 'POST', body: JSON.stringify(payload) }),

  // Standout Feature: Billing Control Tower
  getControlTowerPreview: () => request<any>('/control-tower/preview'),
  commitControlTowerBatch: () =>
    request<any>('/control-tower/commit', { method: 'POST' }),

  // Customer Portal (Derives account from session)
  getPortalSubscriptions: () => request<any[]>('/portal/subscriptions'),
  getPortalInvoices: () => request<any[]>('/portal/invoices'),
  getPortalProfile: () => request<any>('/portal/profile'),
};


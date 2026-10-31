const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/v1';

export type MoneyValue = number | string;

export interface StaffUserItem {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'staff';
  is_active: boolean;
  created_at: string;
}

export interface CreateStaffPayload {
  email: string;
  password: string;
  full_name: string;
  role: 'admin' | 'staff';
  is_active?: boolean;
}

export interface UpdateStaffPayload {
  full_name?: string;
  role?: 'admin' | 'staff';
  is_active?: boolean;
}

export interface AuthProfile {
  user: { id: string; email: string; full_name: string; role: string };
  customer_account?: { company_name: string } | null;
}

export interface ProductApiItem {
  id: string;
  name: string;
  type: string;
  sales_price: MoneyValue;
  cost_price?: MoneyValue | null;
  notes?: string | null;
  variants: { id: string; name: string; price_adjustment: MoneyValue }[];
}

export interface PlanApiItem {
  id: string;
  name: string;
  cadence: string;
  base_price: MoneyValue;
  min_quantity: number;
}

export interface SubscriptionApiItem {
  id: string;
  subscription_number: string;
  customer_name: string;
  plan_name: string;
  status: string;
  total_amount: MoneyValue;
  next_billing_date?: string | null;
  lines: { id: string; product_name?: string | null; quantity: number; unit_price: MoneyValue }[];
}

export interface InvoiceApiItem {
  id: string;
  invoice_number: string;
  customer_name: string;
  billing_period_start: string;
  billing_period_end: string;
  total_amount: MoneyValue;
  paid_amount: MoneyValue;
  due_date: string;
  status: string;
  is_overdue: boolean;
}

export interface PortalProfile {
  company_name: string;
  billing_email: string;
  phone?: string | null;
  tax_id?: string | null;
  billing_address: string;
  currency: string;
}

export interface ControlTowerPreview {
  billing_run_id: string;
  billing_period_start: string;
  billing_period_end: string;
  total_projected_amount: MoneyValue;
  flagged_count: number;
  items: {
    id: string;
    subscription_number: string;
    customer_name: string;
    plan_name: string;
    expected_subtotal: MoneyValue;
    expected_tax_amount: MoneyValue;
    expected_discount_amount: MoneyValue;
    expected_total_amount: MoneyValue;
    prior_invoice_total?: MoneyValue | null;
    variance_amount?: MoneyValue | null;
    variance_reasons: string[];
    warnings: string[];
    status: string;
  }[];
}

export interface DashboardSummary {
  currency: string;
  active_subscription_count: number;
  monthly_recurring_revenue: MoneyValue | null;
  invoiced_mtd: MoneyValue | null;
  cash_collected_mtd: MoneyValue | null;
  outstanding_balance: MoneyValue | null;
  overdue_balance: MoneyValue | null;
  overdue_invoice_count: number;
  pending_quotes_count: number;
  renewals_due_7d_count: number;
}

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
    credentials: 'include',
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

  signup: (payload: Record<string, unknown>) =>
    request<{ access_token: string; token_type: string }>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getMe: () => request<AuthProfile>('/auth/me'),
  forgotPassword: (email: string) =>
    request<{ message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  logout: async () => {
    try {
      await request<{ message: string }>('/auth/logout', { method: 'POST' });
    } catch {
      // Ignore network errors
    }
    localStorage.removeItem('brightloop_jwt_token');
  },
  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    }),

  // Catalog
  getProducts: () => request<ProductApiItem[]>('/products'),
  getPlans: () => request<PlanApiItem[]>('/plans'),

  // Subscriptions
  getSubscriptions: () => request<SubscriptionApiItem[]>('/subscriptions'),
  pauseSubscription: (id: string) =>
    request<{ message: string; status: string }>(`/subscriptions/${id}/pause`, { method: 'POST' }),
  resumeSubscription: (id: string) =>
    request<{ message: string; status: string }>(`/subscriptions/${id}/resume`, { method: 'POST' }),

  // Invoices & Payments
  getInvoices: () => request<InvoiceApiItem[]>('/invoices'),
  recordPayment: (payload: {
    invoice_id: string;
    amount: number;
    payment_method: string;
    payment_date: string;
    reference_note?: string;
  }) => request<{ id: string; invoice_id: string }>('/payments', { method: 'POST', body: JSON.stringify(payload) }),

  // Standout Feature: Billing Control Tower
  getControlTowerPreview: () => request<ControlTowerPreview>('/control-tower/preview', { method: 'POST' }),
  commitControlTowerPreview: (runId: string, approvedItemIds: string[]) =>
    request<{ invoices_created_count: number; total_invoiced_amount: MoneyValue }>(`/control-tower/runs/${runId}/commit`, {
      method: 'POST',
      body: JSON.stringify({ approved_item_ids: approvedItemIds }),
    }),

  getDashboardSummary: () => request<DashboardSummary>('/reports/summary'),

  // Customer Portal (Derives account from session)
  getPortalSubscriptions: () => request<SubscriptionApiItem[]>('/portal/subscriptions'),
  getPortalInvoices: () => request<InvoiceApiItem[]>('/portal/invoices'),
  getPortalProfile: () => request<PortalProfile>('/portal/profile'),

  // Staff & Access Administration (Admin only)
  getStaff: () => request<StaffUserItem[]>('/admin/staff'),
  createStaff: (payload: CreateStaffPayload) =>
    request<StaffUserItem>('/admin/staff', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateStaff: (id: string, payload: UpdateStaffPayload) =>
    request<StaffUserItem>(`/admin/staff/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
};


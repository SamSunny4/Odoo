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
  variants: { id?: string; name: string; price_adjustment: MoneyValue }[];
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
  start_date?: string | null;
  expiry_date?: string | null;
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
  outstanding_balance?: MoneyValue;
  due_date: string;
  issue_date?: string;
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

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface QueryParams {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: string;
  role?: string;
  type?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

function buildQuery(params?: QueryParams): string {
  if (!params) return '';
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) searchParams.set('page', String(params.page));
  if (params.pageSize !== undefined) searchParams.set('page_size', String(params.pageSize));
  if (params.search && params.search.trim()) searchParams.set('search', params.search.trim());
  if (params.status && params.status.trim()) searchParams.set('status', params.status.trim());
  if (params.role && params.role.trim()) searchParams.set('role', params.role.trim());
  if (params.type && params.type.trim()) searchParams.set('type', params.type.trim());
  if (params.sortBy) searchParams.set('sort_by', params.sortBy);
  if (params.sortOrder) searchParams.set('sort_order', params.sortOrder);
  searchParams.set('envelope', 'true');
  const qs = searchParams.toString();
  return qs ? `?${qs}` : '';
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = {
    'Content-Type': 'application/json',
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

async function requestPaginated<T>(endpoint: string, params?: QueryParams): Promise<PaginatedResult<T>> {
  const qs = buildQuery(params);
  const data = await request<{
    items: T[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  }>(`${endpoint}${qs}`);

  return {
    items: data.items || [],
    total: data.total ?? (data.items?.length || 0),
    page: data.page ?? 1,
    pageSize: data.page_size ?? (params?.pageSize || 10),
    totalPages: data.total_pages ?? 1,
  };
}

export const api = {
  // Auth (Relying strictly on secure HTTP-only cookies; zero tokens stored in browser script space)
  login: (email: string, password: string) =>
    request<{ message: string; user: AuthProfile['user'] }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  signup: (payload: Record<string, unknown>) =>
    request<{ message: string; user: AuthProfile['user'] }>('/auth/signup', {
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
  },
  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    }),

  // Catalog
  getProducts: (params?: QueryParams) => requestPaginated<ProductApiItem>('/products', params),
  getPlans: () => request<PlanApiItem[]>('/plans'),

  // Subscriptions
  getSubscriptions: (params?: QueryParams) => requestPaginated<SubscriptionApiItem>('/subscriptions', params),
  pauseSubscription: (id: string) =>
    request<{ message: string; status: string }>(`/subscriptions/${id}/pause`, { method: 'POST' }),
  resumeSubscription: (id: string) =>
    request<{ message: string; status: string }>(`/subscriptions/${id}/resume`, { method: 'POST' }),

  // Invoices & Payments
  getInvoices: (params?: QueryParams) => requestPaginated<InvoiceApiItem>('/invoices', params),
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
  getPortalSubscriptions: (params?: QueryParams) => requestPaginated<SubscriptionApiItem>('/portal/subscriptions', params),
  getPortalInvoices: (params?: QueryParams) => requestPaginated<InvoiceApiItem>('/portal/invoices', params),
  getPortalProfile: () => request<PortalProfile>('/portal/profile'),

  // Staff & Access Administration (Admin only)
  getStaff: (params?: QueryParams) => requestPaginated<StaffUserItem>('/admin/staff', params),
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

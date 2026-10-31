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

export interface ProductVariantApiItem {
  id: string;
  name: string;
  price_adjustment: MoneyValue;
  is_active: boolean;
}

export interface ProductApiItem {
  id: string;
  name: string;
  type: string;
  sales_price: MoneyValue;
  cost_price?: MoneyValue | null;
  notes?: string | null;
  is_add_on?: boolean;
  is_active?: boolean;
  variants: ProductVariantApiItem[];
}

export interface CreateProductPayload {
  name: string;
  type: string;
  sales_price: number | string;
  cost_price: number | string;
  notes?: string;
  is_add_on?: boolean;
  is_active?: boolean;
  variants?: { name: string; price_adjustment: number | string }[];
}

export interface UpdateProductPayload {
  name?: string;
  type?: string;
  sales_price?: number | string;
  cost_price?: number | string;
  notes?: string;
  is_add_on?: boolean;
  is_active?: boolean;
}

export interface PlanApiItem {
  id: string;
  name: string;
  cadence: string;
  base_price: MoneyValue;
  min_quantity: number;
  available_from?: string | null;
  available_to?: string | null;
  auto_close_on_expiry: boolean;
  allow_early_close: boolean;
  allow_pause: boolean;
  allow_renewal: boolean;
  is_active: boolean;
}

export interface CreatePlanPayload {
  name: string;
  cadence: string;
  base_price: number | string;
  min_quantity: number;
  available_from?: string;
  available_to?: string;
  auto_close_on_expiry?: boolean;
  allow_early_close?: boolean;
  allow_pause?: boolean;
  allow_renewal?: boolean;
  is_active?: boolean;
}

export interface UpdatePlanPayload {
  name?: string;
  cadence?: string;
  base_price?: number | string;
  min_quantity?: number;
  available_from?: string | null;
  available_to?: string | null;
  auto_close_on_expiry?: boolean;
  allow_early_close?: boolean;
  allow_pause?: boolean;
  allow_renewal?: boolean;
  is_active?: boolean;
}

export interface TaxRuleApiItem {
  id: string;
  name: string;
  rate_percentage: MoneyValue;
  is_active: boolean;
  created_at?: string;
}

export interface CreateTaxRulePayload {
  name: string;
  rate_percentage: number | string;
  is_active?: boolean;
}

export interface UpdateTaxRulePayload {
  name?: string;
  rate_percentage?: number | string;
  is_active?: boolean;
}

export interface DiscountRuleApiItem {
  id: string;
  name: string;
  discount_type: 'percentage' | 'fixed';
  value: MoneyValue;
  scope: 'subscription' | 'product';
  target_product_id?: string | null;
  target_product_name?: string | null;
  min_spend: MoneyValue;
  min_quantity: number;
  max_usage_limit?: number | null;
  current_usage_count: number;
  valid_from: string;
  valid_to: string;
  is_active: boolean;
  created_at?: string;
}

export interface CreateDiscountRulePayload {
  name: string;
  discount_type: 'percentage' | 'fixed';
  value: number | string;
  scope?: 'subscription' | 'product';
  target_product_id?: string;
  min_spend?: number | string;
  min_quantity?: number;
  max_usage_limit?: number;
  valid_from: string;
  valid_to: string;
  is_active?: boolean;
}

export interface UpdateDiscountRulePayload {
  name?: string;
  discount_type?: 'percentage' | 'fixed';
  value?: number | string;
  scope?: 'subscription' | 'product';
  target_product_id?: string;
  min_spend?: number | string;
  min_quantity?: number;
  max_usage_limit?: number | null;
  valid_from?: string;
  valid_to?: string;
  is_active?: boolean;
}

export interface CalculatePreviewPayload {
  plan_id?: string;
  product_lines: {
    product_id: string;
    variant_id?: string;
    quantity: number;
    tax_rule_id?: string;
  }[];
  discount_rule_id?: string;
  default_tax_rule_id?: string;
  as_of?: string;
}

export interface CalculatePreviewResult {
  plan_name?: string | null;
  plan_base_price: MoneyValue;
  lines: {
    description: string;
    product_name: string;
    variant_name?: string | null;
    price_adjustment: MoneyValue;
    unit_price: MoneyValue;
    quantity: number;
    subtotal: MoneyValue;
    discount_amount: MoneyValue;
    tax_rate: MoneyValue;
    tax_amount: MoneyValue;
    line_total: MoneyValue;
  }[];
  subtotal: MoneyValue;
  discount_amount: MoneyValue;
  discount_name?: string | null;
  tax_amount: MoneyValue;
  total_amount: MoneyValue;
  warnings: string[];
}

export interface QuotationTemplateApiItem {
  id: string;
  name: string;
  validity_days: number;
  default_plan_id?: string | null;
  default_plan_name?: string | null;
  default_lines: {
    product_id: string;
    product_name?: string;
    product_variant_id?: string | null;
    variant_name?: string | null;
    quantity: number;
  }[];
  created_at?: string;
}

export interface CreateQuotationTemplatePayload {
  name: string;
  validity_days: number;
  default_plan_id?: string;
  default_lines?: {
    product_id: string;
    product_variant_id?: string;
    quantity: number;
  }[];
}

export interface UpdateQuotationTemplatePayload {
  name?: string;
  validity_days?: number;
  default_plan_id?: string;
  default_lines?: {
    product_id: string;
    product_variant_id?: string;
    quantity: number;
  }[];
}

export interface SubscriptionAuditItem {
  id: string;
  action: string;
  changes: Record<string, unknown>;
  actor_user_id?: string | null;
  actor_name?: string | null;
  actor_email?: string | null;
  actor_role?: string | null;
  timestamp: string;
}

export interface SubscriptionLineItem {
  id: string;
  product_id: string;
  product_name?: string | null;
  product_variant_id?: string | null;
  variant_name?: string | null;
  quantity: number;
  unit_price: MoneyValue;
  tax_rule_id?: string | null;
  tax_rate?: MoneyValue | null;
  line_subtotal: MoneyValue;
  discount_amount: MoneyValue;
  tax_amount: MoneyValue;
  line_total: MoneyValue;
}

export interface SubscriptionPlanCharge {
  quantity: number;
  unit_price: MoneyValue;
  subtotal: MoneyValue;
  discount_amount: MoneyValue;
  tax_name?: string | null;
  tax_rate: MoneyValue;
  tax_amount: MoneyValue;
  line_total: MoneyValue;
}

export interface SubscriptionDetailApiItem {
  id: string;
  subscription_number: string;
  customer_account_id: string;
  customer_name: string;
  customer_billing_email?: string | null;
  customer_address?: string | null;
  plan_id: string;
  plan_name: string;
  plan_cadence?: string | null;
  plan_base_price: MoneyValue;
  plan_allow_pause: boolean;
  plan_allow_early_close: boolean;
  plan_allow_renewal: boolean;
  plan_auto_close_on_expiry: boolean;
  status: string;
  start_date: string;
  expiry_date?: string | null;
  quote_valid_until?: string | null;
  next_billing_date?: string | null;
  billing_anchor_day: number;
  payment_terms_days: number;
  plan_charge?: SubscriptionPlanCharge | null;
  subtotal_amount: MoneyValue;
  discount_amount: MoneyValue;
  tax_amount: MoneyValue;
  total_amount: MoneyValue;
  calculation_warnings: string[];
  lines: SubscriptionLineItem[];
  audit_history: SubscriptionAuditItem[];
}

export interface CreateSubscriptionPayload {
  customer_account_id: string;
  plan_id: string;
  template_id?: string;
  start_date?: string;
  expiry_date?: string;
  quote_valid_until?: string;
  billing_anchor_day?: number;
  payment_terms_days?: number;
  status?: string;
  lines?: {
    product_id: string;
    product_variant_id?: string;
    quantity: number;
    unit_price?: number | string;
    tax_rule_id?: string;
  }[];
}

export interface UpdateSubscriptionPayload {
  plan_id?: string;
  start_date?: string;
  expiry_date?: string;
  quote_valid_until?: string;
  billing_anchor_day?: number;
  payment_terms_days?: number;
  lines?: {
    product_id: string;
    product_variant_id?: string;
    quantity: number;
    unit_price?: number | string;
    tax_rule_id?: string;
  }[];
}

export interface CustomerAccountApiItem {
  id: string;
  company_name: string;
  billing_email: string;
  currency: string;
}

export interface SubscriptionApiItem {
  id: string;
  subscription_number: string;
  customer_name: string;
  plan_name: string;
  status: string;
  plan_cadence?: string | null;
  plan_allow_pause: boolean;
  plan_allow_early_close: boolean;
  plan_allow_renewal: boolean;
  cancel_at_period_end: boolean;
  plan_charge?: SubscriptionPlanCharge | null;
  subtotal_amount: MoneyValue;
  discount_amount: MoneyValue;
  tax_amount: MoneyValue;
  total_amount: MoneyValue;
  next_billing_date?: string | null;
  start_date?: string | null;
  expiry_date?: string | null;
  quote_valid_until?: string | null;
  lines: {
    id: string;
    product_id: string;
    product_name?: string | null;
    product_is_add_on?: boolean;
    product_variant_id?: string | null;
    variant_name?: string | null;
    quantity: number;
    unit_price: MoneyValue;
    line_subtotal?: MoneyValue;
    discount_amount?: MoneyValue;
    tax_rate?: MoneyValue | null;
    tax_amount?: MoneyValue;
    line_total: MoneyValue;
  }[];
}

export interface PortalPaymentItem {
  id: string;
  invoice_id: string;
  invoice_number: string;
  amount: MoneyValue;
  currency: string;
  payment_method: string;
  payment_date: string;
  reference_note?: string | null;
  is_reversed: boolean;
}

export interface PortalAddonProduct {
  id: string;
  name: string;
  sales_price: MoneyValue;
  variants: { id: string; name: string; price_adjustment: MoneyValue }[];
}

export interface PortalSubscriptionActionPayload {
  action: 'pause' | 'resume' | 'cancel' | 'renew' | 'change_addons';
  reason?: string;
  renewal_duration_days?: number;
  lines?: { product_id: string; product_variant_id?: string; quantity: number }[];
}

export interface PortalSubscriptionActionResult {
  message: string;
  status: string;
  effective_date?: string | null;
  cancel_at_period_end: boolean;
}

export interface OutboxMessageItem {
  id: string;
  topic: string;
  message_type?: string | null;
  recipient?: string | null;
  subject?: string | null;
  status: string;
  retry_count: number;
  max_retries: number;
  last_error?: string | null;
  scheduled_at: string;
  sent_at?: string | null;
  created_at: string;
}

export interface InvoiceLineApiItem {
  id: string;
  description: string;
  product_name_snapshot: string;
  variant_name_snapshot?: string | null;
  quantity: number;
  unit_price_snapshot: MoneyValue;
  subtotal: MoneyValue;
  tax_rule_name_snapshot?: string | null;
  tax_rate_snapshot?: MoneyValue;
  tax_amount: MoneyValue;
  discount_rule_name_snapshot?: string | null;
  discount_amount: MoneyValue;
  line_total: MoneyValue;
}

export interface InvoiceAuditItem {
  id: string;
  action: string;
  changes: Record<string, unknown>;
  actor_user_id?: string | null;
  actor_name: string;
  actor_email?: string | null;
  actor_role?: string | null;
  timestamp: string;
}

export interface InvoiceApiItem {
  id: string;
  invoice_number: string;
  currency?: string;
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
  subtotal?: MoneyValue;
  tax_amount?: MoneyValue;
  discount_amount?: MoneyValue;
  send_status?: string;
  subscription_id?: string;
}

export interface InvoiceDetailApiItem extends InvoiceApiItem {
  customer_snapshot?: Record<string, unknown>;
  billing_address_snapshot?: Record<string, unknown>;
  cancellation_reason?: string | null;
  sent_at?: string | null;
  lines: InvoiceLineApiItem[];
  payments?: {
    id: string;
    amount: MoneyValue;
    payment_method: string;
    payment_date: string;
    reference_note?: string;
    is_reversed: boolean;
  }[];
  audit_history?: InvoiceAuditItem[];
}

export interface BillingRunSummaryApiItem {
  id: string;
  run_date: string;
  billing_period_start: string;
  billing_period_end: string;
  status: string;
  total_evaluated: number;
  total_amount_projected: MoneyValue;
  created_at: string;
  committed_at?: string | null;
  invoices_created_count: number;
  skipped_count: number;
  flagged_count: number;
}

export interface PortalProfile {
  company_name: string;
  billing_email: string;
  phone?: string | null;
  tax_id?: string | null;
  billing_address: string;
  currency: string;
}

export interface ControlTowerItem {
  id: string;
  subscription_id?: string;
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
  skip_reason?: string | null;
  resulting_invoice_id?: string | null;
}

export interface ControlTowerPreview {
  billing_run_id: string;
  billing_period_start: string;
  billing_period_end: string;
  total_projected_amount: MoneyValue;
  flagged_count: number;
  items: ControlTowerItem[];
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
  envelope?: boolean;
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
  if (params.envelope !== false) {
    searchParams.set('envelope', 'true');
  }
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

async function requestBlob(endpoint: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${endpoint}`, { credentials: 'include' });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorBody.detail || `HTTP Error ${response.status}`);
  }
  return response.blob();
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

  // Catalog Products & Variants
  getProducts: (params?: QueryParams) => requestPaginated<ProductApiItem>('/products', params),
  getAllProducts: () => request<ProductApiItem[]>('/products?envelope=false'),
  createProduct: (payload: CreateProductPayload) =>
    request<ProductApiItem>('/products', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateProduct: (id: string, payload: UpdateProductPayload) =>
    request<ProductApiItem>(`/products/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  archiveProduct: (id: string) =>
    request<{ message: string; is_active: boolean }>(`/products/${id}`, {
      method: 'DELETE',
    }),
  getProductVariants: (productId: string) =>
    request<ProductVariantApiItem[]>(`/products/${productId}/variants`),
  createProductVariant: (productId: string, payload: { name: string; price_adjustment: number | string }) =>
    request<ProductVariantApiItem>(`/products/${productId}/variants`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateProductVariant: (
    productId: string,
    variantId: string,
    payload: { name?: string; price_adjustment?: number | string; is_active?: boolean }
  ) =>
    request<ProductVariantApiItem>(`/products/${productId}/variants/${variantId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  archiveProductVariant: (productId: string, variantId: string) =>
    request<{ message: string; is_active: boolean }>(`/products/${productId}/variants/${variantId}`, {
      method: 'DELETE',
    }),

  // Plans Management
  getPlans: () => request<PlanApiItem[]>('/plans'),
  createPlan: (payload: CreatePlanPayload) =>
    request<PlanApiItem>('/plans', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updatePlan: (id: string, payload: UpdatePlanPayload) =>
    request<PlanApiItem>(`/plans/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  archivePlan: (id: string) =>
    request<{ message: string; is_active: boolean }>(`/plans/${id}`, {
      method: 'DELETE',
    }),

  // Tax Rules
  getTaxRules: (params?: QueryParams) => requestPaginated<TaxRuleApiItem>('/tax-rules', params),
  getAllTaxRules: () => request<TaxRuleApiItem[]>('/tax-rules?envelope=false'),
  createTaxRule: (payload: CreateTaxRulePayload) =>
    request<TaxRuleApiItem>('/tax-rules', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateTaxRule: (id: string, payload: UpdateTaxRulePayload) =>
    request<TaxRuleApiItem>(`/tax-rules/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  archiveTaxRule: (id: string) =>
    request<{ message: string; is_active: boolean }>(`/tax-rules/${id}`, {
      method: 'DELETE',
    }),

  // Discount Rules
  getDiscountRules: (params?: QueryParams) => requestPaginated<DiscountRuleApiItem>('/discount-rules', params),
  getAllDiscountRules: () => request<DiscountRuleApiItem[]>('/discount-rules?envelope=false'),
  createDiscountRule: (payload: CreateDiscountRulePayload) =>
    request<DiscountRuleApiItem>('/discount-rules', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateDiscountRule: (id: string, payload: UpdateDiscountRulePayload) =>
    request<DiscountRuleApiItem>(`/discount-rules/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  archiveDiscountRule: (id: string) =>
    request<{ message: string; is_active: boolean }>(`/discount-rules/${id}`, {
      method: 'DELETE',
    }),

  // Quote Simulator / Price Calculation Preview
  calculatePreview: (payload: CalculatePreviewPayload) =>
    request<CalculatePreviewResult>('/catalog/calculate-preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Quotation Templates
  getQuotationTemplates: (params?: QueryParams) =>
    requestPaginated<QuotationTemplateApiItem>('/quotation-templates', params),
  getAllQuotationTemplates: () =>
    request<QuotationTemplateApiItem[]>('/quotation-templates?envelope=false'),
  getQuotationTemplate: (id: string) =>
    request<QuotationTemplateApiItem>(`/quotation-templates/${id}`),
  createQuotationTemplate: (payload: CreateQuotationTemplatePayload) =>
    request<QuotationTemplateApiItem>('/quotation-templates', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateQuotationTemplate: (id: string, payload: UpdateQuotationTemplatePayload) =>
    request<QuotationTemplateApiItem>(`/quotation-templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteQuotationTemplate: (id: string) =>
    request<{ message: string }>(`/quotation-templates/${id}`, {
      method: 'DELETE',
    }),

  // Subscriptions & Quotations Lifecycle
  getSubscriptions: (params?: QueryParams) => requestPaginated<SubscriptionApiItem>('/subscriptions', params),
  getSubscription: (id: string) => request<SubscriptionDetailApiItem>(`/subscriptions/${id}`),
  createSubscription: (payload: CreateSubscriptionPayload) =>
    request<SubscriptionApiItem>('/subscriptions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateSubscription: (id: string, payload: UpdateSubscriptionPayload) =>
    request<SubscriptionApiItem>(`/subscriptions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  transitionSubscriptionStatus: (
    id: string,
    action: string,
    reason?: string,
    renewal_duration_days?: number
  ) =>
    request<SubscriptionApiItem>(`/subscriptions/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ action, reason, renewal_duration_days }),
    }),
  getSubscriptionHistory: (id: string) => request<SubscriptionAuditItem[]>(`/subscriptions/${id}/history`),

  pauseSubscription: (id: string) =>
    request<{ message: string; status: string }>(`/subscriptions/${id}/pause`, { method: 'POST' }),
  resumeSubscription: (id: string) =>
    request<{ message: string; status: string }>(`/subscriptions/${id}/resume`, { method: 'POST' }),

  // Customers for staff/admin selection
  getCustomerAccounts: () => request<CustomerAccountApiItem[]>('/admin/customers'),

  // Invoices & Payments
  getInvoices: (params?: QueryParams) => requestPaginated<InvoiceApiItem>('/invoices', params),
  getInvoice: (id: string) => request<InvoiceDetailApiItem>(`/invoices/${id}`),
  generateDraftInvoice: (payload: {
    subscription_id: string;
    billing_period_start?: string;
    billing_period_end?: string;
    as_draft?: boolean;
  }) =>
    request<InvoiceDetailApiItem>('/invoices/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  confirmInvoice: (id: string) =>
    request<{ message: string; status: string }>(`/invoices/${id}/confirm`, { method: 'POST' }),
  cancelInvoice: (id: string, reason: string) =>
    request<InvoiceDetailApiItem>(`/invoices/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  sendInvoice: (id: string) =>
    request<{ message: string; outbox_message_id: string }>(`/communications/invoices/${id}/send`, { method: 'POST' }),
  getInvoicePdfUrl: (id: string) => `/api/v1/invoices/${id}/pdf`,
  recordPayment: (payload: {
    invoice_id: string;
    amount: number;
    payment_method: string;
    payment_date: string;
    reference_note?: string;
  }) => request<{ id: string; invoice_id: string }>('/payments', { method: 'POST', body: JSON.stringify(payload) }),
  sendQuotationEmail: (id: string) =>
    request<{ message: string; outbox_message_id: string }>(`/communications/subscriptions/${id}/send-quote`, { method: 'POST' }),
  sendInvoiceEmail: (id: string) =>
    request<{ message: string; outbox_message_id: string }>(`/communications/invoices/${id}/send`, { method: 'POST' }),
  getCommunicationsOutbox: (params?: QueryParams) => requestPaginated<OutboxMessageItem>('/communications/outbox', params),
  retryCommunicationEmail: (id: string) =>
    request<OutboxMessageItem>(`/communications/outbox/${id}/retry`, { method: 'POST' }),

  // Standout Feature: Billing Control Tower
  getControlTowerPreview: (batchSize?: number) =>
    request<ControlTowerPreview>(`/control-tower/preview${batchSize ? `?batch_size=${batchSize}` : ''}`, { method: 'POST' }),
  commitControlTowerPreview: (runId: string, approvedItemIds: string[]) =>
    request<{ invoices_created_count: number; total_invoiced_amount: MoneyValue }>(`/control-tower/runs/${runId}/commit`, {
      method: 'POST',
      body: JSON.stringify({ approved_item_ids: approvedItemIds }),
    }),
  getControlTowerRuns: (limit?: number) =>
    request<BillingRunSummaryApiItem[]>(`/control-tower/runs${limit ? `?limit=${limit}` : ''}`),
  getControlTowerRunDetail: (runId: string) =>
    request<ControlTowerPreview>(`/control-tower/runs/${runId}`),
  getControlTowerExceptions: () =>
    request<ControlTowerItem[]>('/control-tower/exceptions'),
  retryControlTowerItem: (itemId: string) =>
    request<{ id: string; status: string; warnings: string[]; message: string }>(`/control-tower/items/${itemId}/retry`, {
      method: 'POST',
    }),
  skipControlTowerItem: (itemId: string, reason: string) =>
    request<ControlTowerItem>(`/control-tower/items/${itemId}/skip`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  triggerAutoBill: () =>
    request<{ status: string; invoices_created: number; emails_queued: number; subscriptions_auto_closed: number }>(
      '/control-tower/auto-bill',
      { method: 'POST' }
    ),

  getDashboardSummary: () => request<DashboardSummary>('/reports/summary'),

  // Customer Portal (Derives account from session)
  getPortalSubscriptions: (params?: QueryParams) => requestPaginated<SubscriptionApiItem>('/portal/subscriptions', params),
  getPortalInvoices: (params?: QueryParams) => requestPaginated<InvoiceApiItem>('/portal/invoices', params),
  getPortalPayments: (params?: QueryParams) => requestPaginated<PortalPaymentItem>('/portal/payments', params),
  getPortalProfile: () => request<PortalProfile>('/portal/profile'),
  getPortalAddonCatalog: () => request<PortalAddonProduct[]>('/portal/catalog/addons'),
  performPortalSubscriptionAction: (id: string, payload: PortalSubscriptionActionPayload) =>
    request<PortalSubscriptionActionResult>(`/portal/subscriptions/${id}/actions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  downloadPortalInvoicePdf: (id: string) => requestBlob(`/portal/invoices/${id}/pdf`),

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

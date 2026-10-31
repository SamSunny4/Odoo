import re

with open('frontend/src/services/api.ts', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add saveBlobAsFile after requestBlob
blob_helper = '''
export function saveBlobAsFile(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}
'''
if 'export function saveBlobAsFile' not in content:
    content = content.replace(
        'return response.blob();\r\n}',
        'return response.blob();\r\n}\r\n' + blob_helper
    )
    content = content.replace(
        'return response.blob();\n}',
        'return response.blob();\n}\n' + blob_helper
    )

# 2. Add downloadReportCsv and downloadControlTowerRunCsv before getReportExportUrl
new_methods = '''  downloadReportCsv: async (params: {
    metric: string;
    period?: string;
    start_date?: string;
    end_date?: string;
    plan_id?: string;
    customer_account_id?: string;
    status?: string;
    search?: string;
  }) => {
    const q = new URLSearchParams();
    q.append('metric', params.metric);
    if (params.period) q.append('period', params.period);
    if (params.start_date) q.append('start_date', params.start_date);
    if (params.end_date) q.append('end_date', params.end_date);
    if (params.plan_id) q.append('plan_id', params.plan_id);
    if (params.customer_account_id) q.append('customer_account_id', params.customer_account_id);
    if (params.status) q.append('status', params.status);
    if (params.search) q.append('search', params.search);
    const blob = await requestBlob(`/reports/export?${q.toString()}`);
    const today = new Date().toISOString().split('T')[0];
    saveBlobAsFile(blob, `brightloop_finance_${params.metric}_${today}.csv`);
  },
  downloadControlTowerRunCsv: async (runId: string) => {
    const blob = await requestBlob(`/control-tower/runs/${runId}/export`);
    saveBlobAsFile(blob, `billing_run_${runId}.csv`);
  },
'''

if 'downloadReportCsv' not in content:
    content = content.replace(
        '  getReportExportUrl:',
        new_methods + '  getReportExportUrl:'
    )

# 3. Update export URLs to include API_BASE
content = content.replace(
    'return `/api/v1/reports/export?',
    'return `${API_BASE}/reports/export?'
)
content = content.replace(
    'getControlTowerRunExportUrl: (runId: string) => `/api/v1/control-tower/runs/${runId}/export`',
    'getControlTowerRunExportUrl: (runId: string) => `${API_BASE}/control-tower/runs/${runId}/export`'
)

with open('frontend/src/services/api.ts', 'w', encoding='utf-8') as f:
    f.write(content)

print("api.ts successfully patched!")

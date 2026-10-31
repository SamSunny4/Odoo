with open('frontend/src/pages/Dashboard.tsx', 'r', encoding='utf-8') as f:
    dash = f.read()

# Add isExporting state
if 'const [isExporting, setIsExporting]' not in dash:
    dash = dash.replace(
        "const [showDefinitions, setShowDefinitions] = useState<boolean>(false);",
        "const [showDefinitions, setShowDefinitions] = useState<boolean>(false);\n  const [isExporting, setIsExporting] = useState<boolean>(false);"
    )

old_handle = '''  const handleExportCsv = () => {
    const exportUrl = api.getReportExportUrl({
      metric: activeMetric,
      period,
      plan_id: drillPlanId || undefined,
      customer_account_id: drillCustomerId || undefined,
      status: drillStatus || undefined,
      search: drillSearch || undefined,
    });
    window.open(exportUrl, '_blank');
  };'''

new_handle = '''  const handleExportCsv = async () => {
    try {
      setIsExporting(true);
      await api.downloadReportCsv({
        metric: activeMetric,
        period,
        plan_id: drillPlanId || undefined,
        customer_account_id: drillCustomerId || undefined,
        status: drillStatus || undefined,
        search: drillSearch || undefined,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to export CSV report';
      setError(msg);
    } finally {
      setIsExporting(false);
    }
  };'''

dash = dash.replace(old_handle.replace('\r\n', '\n'), new_handle)
dash = dash.replace(old_handle.replace('\n', '\r\n'), new_handle.replace('\n', '\r\n'))

dash = dash.replace(
    'title="Export current financial dataset to CSV"\n              >\n                <Download className="w-4 h-4 text-slate-500" />\n                Export CSV',
    'disabled={isExporting}\n                title="Export current financial dataset to CSV"\n              >\n                <Download className="w-4 h-4 text-slate-500" />\n                {isExporting ? \'Exporting...\' : \'Export CSV\'}'
)
dash = dash.replace(
    'title="Export current financial dataset to CSV"\r\n              >\r\n                <Download className="w-4 h-4 text-slate-500" />\r\n                Export CSV',
    'disabled={isExporting}\r\n                title="Export current financial dataset to CSV"\r\n              >\r\n                <Download className="w-4 h-4 text-slate-500" />\r\n                {isExporting ? \'Exporting...\' : \'Export CSV\'}'
)

dash = dash.replace(
    '<Download className="w-3.5 h-3.5 text-slate-500" />\n                Export Ledger CSV',
    '<Download className="w-3.5 h-3.5 text-slate-500" />\n                {isExporting ? \'Exporting...\' : \'Export Ledger CSV\'}'
)
dash = dash.replace(
    '<Download className="w-3.5 h-3.5 text-slate-500" />\r\n                Export Ledger CSV',
    '<Download className="w-3.5 h-3.5 text-slate-500" />\r\n                {isExporting ? \'Exporting...\' : \'Export Ledger CSV\'}'
)

with open('frontend/src/pages/Dashboard.tsx', 'w', encoding='utf-8') as f:
    f.write(dash)
print("Dashboard.tsx updated")

# ControlTower.tsx
with open('frontend/src/pages/ControlTower.tsx', 'r', encoding='utf-8') as f:
    ct = f.read()

old_ct_link = '''                {runId && (
                  <a
                    href={api.getControlTowerRunExportUrl(runId)}
                    target="_blank"
                    rel="noreferrer"
                    className="px-2.5 py-1 border border-slate-200 text-slate-700 bg-white hover:bg-slate-50 text-xs font-semibold rounded-md shadow-2xs flex items-center gap-1 transition ml-2"
                    title="Export preview batch to CSV"
                  >
                    <Download className="w-3.5 h-3.5 text-slate-500" />
                    Export CSV
                  </a>
                )}'''

new_ct_button = '''                {runId && (
                  <button
                    onClick={async () => {
                      try {
                        await api.downloadControlTowerRunCsv(runId);
                      } catch (err: unknown) {
                        const msg = err instanceof Error ? err.message : 'Failed to export run CSV';
                        setError(msg);
                      }
                    }}
                    className="px-2.5 py-1 border border-slate-200 text-slate-700 bg-white hover:bg-slate-50 text-xs font-semibold rounded-md shadow-2xs flex items-center gap-1 transition ml-2"
                    title="Export preview batch to CSV"
                  >
                    <Download className="w-3.5 h-3.5 text-slate-500" />
                    Export CSV
                  </button>
                )}'''

ct = ct.replace(old_ct_link.replace('\r\n', '\n'), new_ct_button)
ct = ct.replace(old_ct_link.replace('\n', '\r\n'), new_ct_button.replace('\n', '\r\n'))

with open('frontend/src/pages/ControlTower.tsx', 'w', encoding='utf-8') as f:
    f.write(ct)
print("ControlTower.tsx updated")

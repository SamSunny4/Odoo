import React, { useState } from 'react';
import { api } from '../services/api';

export const ResetPassword: React.FC = () => {
  const token = new URLSearchParams(window.location.search).get('token') || '';
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (!token) {
      setError('This reset link is missing its token. Request a new one from the sign-in page.');
      return;
    }
    if (password !== confirmation) {
      setError('The passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const result = await api.resetPassword(token, password);
      setSuccess(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not reset your password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
        <div className="h-12 w-12 bg-indigo-600 rounded-xl flex items-center justify-center text-white font-bold text-2xl">B</div>
        <h1 className="mt-5 text-2xl font-bold text-slate-900">Choose a new password</h1>
        <p className="mt-2 text-sm text-slate-500">Use more than 8 characters with uppercase, lowercase, and a special character.</p>
        {error && <div role="alert" className="mt-5 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3">{error}</div>}
        {success ? (
          <div className="mt-5 space-y-4">
            <div role="status" className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm rounded-lg p-3">{success}</div>
            <a href="/" className="block text-center py-2.5 rounded-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700">Return to sign in</a>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-5 space-y-4">
            <label className="block text-sm font-medium text-slate-700">
              New password
              <input type="password" required minLength={9} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg" />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Confirm new password
              <input type="password" required minLength={9} autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg" />
            </label>
            <button type="submit" disabled={loading} className="w-full py-2.5 rounded-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60">
              {loading ? 'Updating…' : 'Update password'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

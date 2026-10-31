import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Lock, Mail } from 'lucide-react';
import { api } from '../services/api';

export const Login: React.FC = () => {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<'login' | 'signup' | 'forgot'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [country, setCountry] = useState('US');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signup({
        email,
        password,
        full_name: fullName,
        company_name: companyName,
        billing_address_line1: address,
        billing_city: city,
        billing_postal_code: postalCode,
        billing_country: country,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed. Check password requirements.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const result = await api.forgotPassword(email);
      setNotice(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not request a password reset.');
    } finally {
      setLoading(false);
    }
  };

  const fillQuickDemo = (demoEmail: string, demoPass: string) => {
    setMode('login');
    setEmail(demoEmail);
    setPassword(demoPass);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="h-12 w-12 bg-indigo-600 rounded-xl mx-auto flex items-center justify-center text-white font-bold text-2xl shadow-sm">
          B
        </div>
        <h2 className="mt-4 text-3xl font-extrabold text-slate-900 tracking-tight">Brightloop Software</h2>
        <p className="mt-1 text-sm text-slate-600">Unified Subscription & Recurring Billing OS</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-sm border border-slate-200 sm:rounded-2xl sm:px-10">
          {/* Mode Switch Tabs */}
          <div className="flex border-b border-slate-200 mb-6">
            <button
              onClick={() => { setMode('login'); setError(null); setNotice(null); }}
              className={`flex-1 py-2 text-center text-sm font-semibold border-b-2 transition ${
                mode === 'login'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode('signup'); setError(null); setNotice(null); }}
              className={`flex-1 py-2 text-center text-sm font-semibold border-b-2 transition ${
                mode === 'signup'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              Customer Sign Up
            </button>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg p-3">
              {error}
            </div>
          )}
          {notice && (
            <div className="mb-4 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg p-3">
              {notice}
            </div>
          )}

          {mode === 'forgot' ? (
            <form onSubmit={handleForgotSubmit} className="space-y-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Reset your password</h3>
                <p className="text-sm text-slate-500 mt-1">Enter your account email and we’ll send a secure reset link if it’s registered.</p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">Email Address</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                />
              </div>
              <button type="submit" disabled={loading} className="w-full py-2.5 px-4 rounded-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60">
                {loading ? 'Sending…' : 'Send reset link'}
              </button>
              <button type="button" onClick={() => { setMode('login'); setNotice(null); setError(null); }} className="w-full text-sm text-indigo-600 hover:text-indigo-800">
                Back to sign in
              </button>
            </form>
          ) : mode === 'login' ? (
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">Email Address</label>
                <div className="mt-1 relative rounded-md shadow-xs">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Mail className="h-4 w-4" />
                  </div>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@company.com"
                    className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">Password</label>
                <div className="mt-1 relative rounded-md shadow-xs">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Lock className="h-4 w-4" />
                  </div>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-lg shadow-xs text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition"
              >
                {loading ? 'Authenticating...' : 'Sign In to Dashboard'}
              </button>
              <button type="button" onClick={() => { setMode('forgot'); setError(null); setNotice(null); }} className="w-full text-sm text-indigo-600 hover:text-indigo-800">
                Forgot password?
              </button>
            </form>
          ) : (
            <form onSubmit={handleSignupSubmit} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">Full Name</label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Alex Mercer"
                  className="mt-1 block w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">Work Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@acme.com"
                  className="mt-1 block w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Password <span className="text-[10px] text-slate-400 font-normal">(&gt;8 chars, upper, lower, special)</span>
                </label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Customer@12345!"
                  className="mt-1 block w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">Company Name</label>
                <input
                  type="text"
                  required
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Acme Corporation"
                  className="mt-1 block w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">Address</label>
                  <input
                    type="text"
                    required
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    placeholder="100 Innovation Way"
                    className="mt-1 block w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">City</label>
                  <input
                    type="text"
                    required
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="Austin"
                    className="mt-1 block w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">Zip / Postal</label>
                  <input
                    type="text"
                    required
                    value={postalCode}
                    onChange={(e) => setPostalCode(e.target.value)}
                    placeholder="78701"
                    className="mt-1 block w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">Country</label>
                  <input
                    type="text"
                    required
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    placeholder="US"
                    className="mt-1 block w-full px-3 py-1.5 border border-slate-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 flex justify-center py-2.5 px-4 border border-transparent rounded-lg shadow-xs text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition"
              >
                {loading ? 'Creating Account...' : 'Create Customer Account'}
              </button>
            </form>
          )}

          {/* Seeded Account Quick-Fill Helper */}
          {mode !== 'forgot' && <div className="mt-6 pt-5 border-t border-slate-200">
            <span className="text-xs text-slate-400 block font-medium mb-2">Test with Seeded Accounts:</span>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <button
                type="button"
                onClick={() => fillQuickDemo('admin@brightloop.local', 'Admin@12345!')}
                className="bg-slate-50 border border-slate-200 p-2 rounded-lg text-center hover:bg-indigo-50 hover:border-indigo-200 transition"
              >
                <div className="font-semibold text-slate-800">Admin</div>
                <div className="text-[10px] text-slate-400">admin@...</div>
              </button>
              <button
                type="button"
                onClick={() => fillQuickDemo('staff@brightloop.local', 'Staff@12345!')}
                className="bg-slate-50 border border-slate-200 p-2 rounded-lg text-center hover:bg-emerald-50 hover:border-emerald-200 transition"
              >
                <div className="font-semibold text-slate-800">Staff</div>
                <div className="text-[10px] text-slate-400">staff@...</div>
              </button>
              <button
                type="button"
                onClick={() => fillQuickDemo('customer@acme.com', 'Customer@12345!')}
                className="bg-slate-50 border border-slate-200 p-2 rounded-lg text-center hover:bg-blue-50 hover:border-blue-200 transition"
              >
                <div className="font-semibold text-slate-800">Customer</div>
                <div className="text-[10px] text-slate-400">customer@...</div>
              </button>
            </div>
          </div>}
        </div>
      </div>
    </div>
  );
};

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { apiGet, apiPost, clearTokens, getAccessToken, setTokens } from '../api/client';
import type { LoginResponse, User } from '../api/types';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      if (!getAccessToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await apiGet<User>('/users/me');
        setUser(me);
      } catch {
        clearTokens();
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiPost<LoginResponse>('/auth/login', { username, password });
    setTokens(res.access_token, res.refresh_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    // Best-effort server-side revocation; the contract says logout revokes the refresh token.
    apiPost('/auth/logout').catch(() => undefined);
    clearTokens();
    setUser(null);
    window.location.assign('/login');
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

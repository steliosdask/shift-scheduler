import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { api, getAuthToken, setAuthToken, clearAuthToken } from './api';

type User = { id: string; email: string; name: string; role: string };

type AuthCtx = {
  user: User | null | undefined; // undefined=loading, null=not-authed
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthCtx>({ user: undefined, login: async () => {}, logout: async () => {} });

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    (async () => {
      const t = await getAuthToken();
      if (!t) {
        setUser(null);
        return;
      }
      try {
        const r = await api.get('/auth/me');
        setUser(r.data);
      } catch {
        await clearAuthToken();
        setUser(null);
      }
    })();
  }, []);

  const login = async (email: string, password: string) => {
    const r = await api.post('/auth/login', { email, password });
    await setAuthToken(r.data.access_token);
    setUser(r.data.user);
  };

  const logout = async () => {
    try { await api.post('/auth/logout'); } catch {}
    await clearAuthToken();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

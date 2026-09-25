import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { api, getAuthToken, saveSession, cacheUser, getCachedUser, clearSession } from './api';

type User = { id: string; username: string; role: string };

type AuthCtx = {
  user: User | null | undefined; // undefined=loading, null=not-authed
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthCtx>({ user: undefined, login: async () => {}, logout: async () => {} });

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    (async () => {
      if (!(await getAuthToken())) {
        setUser(null);
        return;
      }
      try {
        const r = await api.get('/auth/me');
        await cacheUser(r.data);
        setUser(r.data);
      } catch (e: any) {
        // A 401 means the session is over (the api interceptor already cleared it).
        // Any other failure means the server is unreachable, so stay signed in.
        setUser(e?.response?.status === 401 ? null : await getCachedUser());
      }
    })();
  }, []);

  const login = async (username: string, password: string) => {
    const r = await api.post('/auth/login', { username, password });
    await saveSession(r.data.access_token, r.data.user);
    setUser(r.data.user);
  };

  const logout = async () => {
    await clearSession();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

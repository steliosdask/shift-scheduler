import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

export const api = axios.create({
  baseURL: `${BASE_URL}/api`,
  // The free server sleeps when idle and can take up to a minute to wake up.
  timeout: 90000,
});

api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers = config.headers || {};
    (config.headers as any).Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err?.response?.status === 401) {
      await clearSession();
    }
    return Promise.reject(err);
  }
);

export const formatApiError = (e: any): string => {
  if (e?.isAxiosError && !e.response) {
    return 'Δεν ήταν δυνατή η σύνδεση με τον server. Ελέγξτε τη σύνδεση στο internet και δοκιμάστε ξανά.';
  }
  const detail = e?.response?.data?.detail;
  if (!detail) return e?.response ? `Σφάλμα server (${e.response.status})` : e?.message || 'Άγνωστο σφάλμα';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((x: any) => x?.msg || JSON.stringify(x)).join(' • ');
  return String(detail);
};

export const getAuthToken = () => AsyncStorage.getItem(TOKEN_KEY);

export const saveSession = (token: string, user: object) =>
  AsyncStorage.multiSet([
    [TOKEN_KEY, token],
    [USER_KEY, JSON.stringify(user)],
  ]);

export const cacheUser = (user: object) => AsyncStorage.setItem(USER_KEY, JSON.stringify(user));

export const getCachedUser = async () => {
  const raw = await AsyncStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
};

export const clearSession = () => AsyncStorage.multiRemove([TOKEN_KEY, USER_KEY]);

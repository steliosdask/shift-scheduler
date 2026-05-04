import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export const api = axios.create({
  baseURL: `${BASE_URL}/api`,
  timeout: 30000,
});

// Inject token automatically
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('auth_token');
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
      await AsyncStorage.removeItem('auth_token');
    }
    return Promise.reject(err);
  }
);

export const formatApiError = (e: any): string => {
  const detail = e?.response?.data?.detail;
  if (!detail) return e?.message || 'Σφάλμα δικτύου';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((x: any) => x?.msg || JSON.stringify(x)).join(' • ');
  return String(detail);
};

export const getAuthToken = () => AsyncStorage.getItem('auth_token');
export const setAuthToken = (t: string) => AsyncStorage.setItem('auth_token', t);
export const clearAuthToken = () => AsyncStorage.removeItem('auth_token');

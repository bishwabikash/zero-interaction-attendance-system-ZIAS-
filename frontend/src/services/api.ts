import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('zias.token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('zias.token');
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    },
);

export const authAPI = {
    login: (username: string, password: string) =>
        api.post('/api/v1/auth/login', { username, password }),
    me: () => api.get('/api/v1/auth/me'),
};

export const attendanceAPI = {
    getRecords: (params?: Record<string, unknown>) =>
        api.get('/api/v1/attendance/records', { params }),
    getRealtimeOccupancy: (room: string) =>
        api.get(`/api/v1/attendance/realtime/${encodeURIComponent(room)}`),
    getSummary: (studentId: string, month?: number, year?: number) =>
        api.get(`/api/v1/attendance/summary/${encodeURIComponent(studentId)}`, {
            params: { month, year },
        }),
    getStats: () => api.get('/api/v1/attendance/stats'),
};

export const devicesAPI = {
    list: () => api.get('/api/v1/devices'),
    register: (data: Record<string, unknown>) =>
        api.post('/api/v1/devices/register', data),
};

export const studentsAPI = {
    list: (params?: Record<string, unknown>) =>
        api.get('/api/v1/students', { params }),
    get: (id: string) => api.get(`/api/v1/students/${encodeURIComponent(id)}`),
    create: (data: Record<string, unknown>) =>
        api.post('/api/v1/students', data),
};

export default api;

import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import type { ApiErrorBody } from '../utils/errorCodes'

export const axiosInstance = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

axiosInstance.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

axiosInstance.interceptors.response.use(
  (res) => res,
  (error: AxiosError<ApiErrorBody>) => {
    if (error.response?.status === 401) {
      const skipRedirect = error.config?.url?.includes('/auth/login')
      if (!skipRedirect) {
        localStorage.removeItem('access_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export const apiClient = <T>(config: AxiosRequestConfig): Promise<T> => {
  return axiosInstance(config).then((res) => res.data as T)
}

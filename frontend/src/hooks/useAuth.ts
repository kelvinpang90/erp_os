import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { axiosInstance } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import type { MeResponse, TokenResponse } from '../types/auth'

export function useAuth() {
  const navigate = useNavigate()
  const { setTokens, setMe, logout: storeLogout, isAuthenticated, user, permissions } =
    useAuthStore()

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await axiosInstance.post<TokenResponse>('/auth/login', { email, password })
      setTokens(res.data.access_token, res.data.refresh_token)

      const meRes = await axiosInstance.get<MeResponse>('/auth/me')
      setMe(meRes.data)

      navigate('/')
    },
    [setTokens, setMe, navigate],
  )

  const logout = useCallback(async () => {
    try {
      await axiosInstance.post('/auth/logout')
    } catch {
      // ignore errors on logout
    } finally {
      storeLogout()
      navigate('/login')
    }
  }, [storeLogout, navigate])

  return { login, logout, isAuthenticated, user, permissions }
}

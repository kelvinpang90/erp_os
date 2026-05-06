import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AISettingsSnapshot, MeResponse, UserProfile, MenuItem } from '../types/auth'

interface AuthState {
  user: UserProfile | null
  permissions: string[]
  menu: MenuItem[]
  demoMode: boolean
  aiSettings: AISettingsSnapshot
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  setTokens: (access: string, refresh: string) => void
  setMe: (me: MeResponse) => void
  logout: () => void
  hasPermission: (code: string) => boolean
}

const DEFAULT_AI_SETTINGS: AISettingsSnapshot = {
  master_enabled: false,
  features: {},
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      permissions: [],
      menu: [],
      demoMode: false,
      aiSettings: DEFAULT_AI_SETTINGS,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      setTokens: (access, refresh) => {
        localStorage.setItem('access_token', access)
        set({ accessToken: access, refreshToken: refresh, isAuthenticated: true })
      },

      setMe: (me) =>
        set({
          user: me.user,
          permissions: me.permissions,
          menu: me.menu,
          demoMode: me.demo_mode ?? false,
          aiSettings: me.ai_settings ?? DEFAULT_AI_SETTINGS,
        }),

      logout: () => {
        localStorage.removeItem('access_token')
        set({
          user: null,
          permissions: [],
          menu: [],
          demoMode: false,
          aiSettings: DEFAULT_AI_SETTINGS,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        })
      },

      hasPermission: (code) => get().permissions.includes(code),
    }),
    {
      name: 'erp-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
        user: state.user,
        permissions: state.permissions,
        menu: state.menu,
        demoMode: state.demoMode,
        aiSettings: state.aiSettings,
      }),
    },
  ),
)

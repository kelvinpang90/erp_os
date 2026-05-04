import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'light' | 'dark'

interface ThemeState {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
  toggle: () => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: 'light',
      setMode: (mode) => {
        set({ mode })
        document.body.dataset.theme = mode
      },
      toggle: () => {
        const next: ThemeMode = get().mode === 'light' ? 'dark' : 'light'
        set({ mode: next })
        document.body.dataset.theme = next
      },
    }),
    {
      name: 'erp-theme',
      onRehydrateStorage: () => (state) => {
        if (state) {
          document.body.dataset.theme = state.mode
        }
      },
    },
  ),
)

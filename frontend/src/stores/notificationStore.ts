import { create } from 'zustand'
import { axiosInstance } from '../api/client'

export type NotificationSeverity = 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR' | 'CRITICAL'

export interface NotificationItem {
  id: number
  type: string
  title: string
  body: string | null
  i18n_key: string | null
  i18n_params: Record<string, unknown> | null
  target_user_id: number | null
  target_role: string | null
  related_entity_type: string | null
  related_entity_id: number | null
  action_url: string | null
  severity: NotificationSeverity
  is_read: boolean
  read_at: string | null
  created_at: string
}

interface NotificationState {
  items: NotificationItem[]
  unread: number
  loading: boolean
  pollTimer: ReturnType<typeof setInterval> | null
  fetchUnreadCount: () => Promise<void>
  fetchList: () => Promise<void>
  markRead: (id: number) => Promise<void>
  markAllRead: () => Promise<void>
  startPolling: () => void
  stopPolling: () => void
  reset: () => void
}

const POLL_INTERVAL_MS = 30_000

export const useNotificationStore = create<NotificationState>((set, get) => ({
  items: [],
  unread: 0,
  loading: false,
  pollTimer: null,

  fetchUnreadCount: async () => {
    try {
      const res = await axiosInstance.get<{ unread: number }>('/notifications/unread-count')
      set({ unread: res.data.unread })
    } catch {
      // Silent — polling failures must not interrupt the UI.
    }
  },

  fetchList: async () => {
    set({ loading: true })
    try {
      const res = await axiosInstance.get<{ items: NotificationItem[]; total: number }>(
        '/notifications',
        { params: { page: 1, page_size: 20 } },
      )
      set({ items: res.data.items })
      const unread = res.data.items.filter((n) => !n.is_read).length
      // The bell badge is count of all unread, not just first page; refresh count too.
      get().fetchUnreadCount()
      if (unread === res.data.items.length && res.data.items.length === 0) {
        set({ unread: 0 })
      }
    } finally {
      set({ loading: false })
    }
  },

  markRead: async (id) => {
    await axiosInstance.post(`/notifications/${id}/read`)
    set((state) => ({
      items: state.items.map((n) =>
        n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n,
      ),
      unread: Math.max(0, state.unread - 1),
    }))
  },

  markAllRead: async () => {
    await axiosInstance.post('/notifications/read-all')
    set((state) => ({
      items: state.items.map((n) => ({ ...n, is_read: true })),
      unread: 0,
    }))
  },

  startPolling: () => {
    const existing = get().pollTimer
    if (existing) return
    void get().fetchUnreadCount()
    const timer = setInterval(() => {
      void get().fetchUnreadCount()
    }, POLL_INTERVAL_MS)
    set({ pollTimer: timer })
  },

  stopPolling: () => {
    const timer = get().pollTimer
    if (timer) {
      clearInterval(timer)
      set({ pollTimer: null })
    }
  },

  reset: () => {
    get().stopPolling()
    set({ items: [], unread: 0, loading: false })
  },
}))

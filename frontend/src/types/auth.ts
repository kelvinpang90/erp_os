export interface MenuItem {
  key: string
  path: string
  icon: string
  label: string
  children: MenuItem[]
}

export interface UserProfile {
  id: number
  organization_id: number
  email: string
  full_name: string
  avatar_url: string | null
  locale: string
  theme: string
  last_login_at: string | null
}

export interface AISettingsSnapshot {
  master_enabled: boolean
  features: Record<string, boolean>
}

export interface MeResponse {
  user: UserProfile
  permissions: string[]
  menu: MenuItem[]
  demo_mode: boolean
  ai_settings: AISettingsSnapshot
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

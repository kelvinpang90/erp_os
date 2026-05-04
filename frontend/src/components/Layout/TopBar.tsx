import {
  BellOutlined,
  GlobalOutlined,
  LogoutOutlined,
  MoonOutlined,
  SunOutlined,
  UserSwitchOutlined,
} from '@ant-design/icons'
import { Avatar, Badge, Drawer, Dropdown, Empty, Modal, Space, Tag } from 'antd'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../hooks/useAuth'
import { useThemeStore } from '../../stores/themeStore'

export default function TopBar() {
  const { t, i18n } = useTranslation('menu')
  const { logout, user } = useAuth()
  const mode = useThemeStore((s) => s.mode)
  const toggleTheme = useThemeStore((s) => s.toggle)
  const [notifyOpen, setNotifyOpen] = useState(false)
  const [roleSwitchOpen, setRoleSwitchOpen] = useState(false)

  const currentLang = i18n.language?.startsWith('zh') ? 'zh-CN' : 'en-US'
  const isAdmin = user?.email === 'admin@demo.my'
  const demoMode = (import.meta.env.VITE_DEMO_MODE ?? 'true') !== 'false'

  const langItems = [
    { key: 'en-US', label: 'English', onClick: () => i18n.changeLanguage('en-US') },
    { key: 'zh-CN', label: '中文', onClick: () => i18n.changeLanguage('zh-CN') },
  ]

  const avatarItems = [
    ...(isAdmin
      ? [
          {
            key: 'switch-role',
            icon: <UserSwitchOutlined />,
            label: t('switchRole'),
            onClick: () => setRoleSwitchOpen(true),
          },
          { type: 'divider' as const },
        ]
      : []),
    { key: 'logout', icon: <LogoutOutlined />, label: t('logout'), onClick: logout },
  ]

  return (
    <Space size="middle" align="center">
      {demoMode && (
        <Tag color="success" style={{ margin: 0 }}>
          🟢 {t('demoMode')}
        </Tag>
      )}

      <Dropdown menu={{ items: langItems, selectedKeys: [currentLang] }}>
        <span style={topBarItemStyle}>
          <GlobalOutlined />
          <span style={{ fontSize: 13 }}>{currentLang === 'zh-CN' ? '中文' : 'EN'}</span>
        </span>
      </Dropdown>

      <span style={topBarItemStyle} onClick={toggleTheme} role="button" aria-label="toggle theme">
        {mode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
      </span>

      <Badge count={0} size="small" offset={[-2, 4]}>
        <span style={topBarItemStyle} onClick={() => setNotifyOpen(true)} role="button" aria-label="notifications">
          <BellOutlined />
        </span>
      </Badge>

      <Dropdown menu={{ items: avatarItems }} placement="bottomRight">
        <Space size={6} style={{ cursor: 'pointer', padding: '0 8px' }}>
          <Avatar size="small">{(user?.full_name ?? user?.email ?? 'U').charAt(0).toUpperCase()}</Avatar>
          <span style={{ fontSize: 13 }}>{user?.full_name ?? user?.email ?? 'User'}</span>
        </Space>
      </Dropdown>

      <Drawer
        title={t('notifications')}
        placement="right"
        width={360}
        open={notifyOpen}
        onClose={() => setNotifyOpen(false)}
      >
        <Empty description={t('notificationsPlaceholder')} />
      </Drawer>

      <Modal
        title={t('switchRole')}
        open={roleSwitchOpen}
        onCancel={() => setRoleSwitchOpen(false)}
        footer={null}
      >
        <Empty description={t('switchRolePlaceholder')} />
      </Modal>
    </Space>
  )
}

const topBarItemStyle: React.CSSProperties = {
  cursor: 'pointer',
  padding: '0 6px',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  fontSize: 16,
}

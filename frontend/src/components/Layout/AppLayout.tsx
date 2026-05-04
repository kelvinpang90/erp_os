import {
  AppstoreOutlined,
  BarChartOutlined,
  DashboardOutlined,
  GlobalOutlined,
  LogoutOutlined,
  ShoppingCartOutlined,
  ShoppingOutlined,
  SettingOutlined,
  TagsOutlined,
} from '@ant-design/icons'
import { ProLayout } from '@ant-design/pro-components'
import { Dropdown } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../hooks/useAuth'
import { useAuthStore } from '../../stores/authStore'

// Top-level paths that require role-based visibility check.
// Items not in this set are always visible (e.g., Dashboard, SKUs).
// The backend's /api/auth/me menu is the source of truth for visibility:
// if a frontend item's path is in ROLE_GATED_PATHS, it's only shown when the
// backend menu (already role-filtered) contains a node with the same path.
const ROLE_GATED_PATHS = new Set(['/purchase', '/sales', '/inventory', '/reports', '/settings'])

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { logout, user } = useAuth()
  const { t, i18n } = useTranslation('menu')
  const backendMenu = useAuthStore((s) => s.menu)

  const currentLang = i18n.language?.startsWith('zh') ? 'zh-CN' : 'en-US'

  const allMenuItems = [
    {
      path: '/',
      name: t('dashboard'),
      icon: <DashboardOutlined />,
    },
    {
      path: '/skus',
      name: t('skuManagement'),
      icon: <TagsOutlined />,
    },
    {
      path: '/purchase',
      name: t('purchase'),
      icon: <ShoppingCartOutlined />,
      children: [
        { path: '/purchase/orders', name: t('purchaseOrders') },
        { path: '/purchase/goods-receipts', name: t('goodsReceipt') },
        { path: '/purchase/suppliers', name: t('suppliers') },
      ],
    },
    {
      path: '/sales',
      name: t('sales'),
      icon: <ShoppingOutlined />,
      children: [
        { path: '/sales/orders', name: t('salesOrders') },
        { path: '/sales/delivery', name: t('deliveryOrders') },
        { path: '/sales/einvoice', name: t('einvoice') },
        { path: '/sales/credit-notes', name: t('creditNotes') },
        { path: '/sales/customers', name: t('customers') },
      ],
    },
    {
      path: '/inventory',
      name: t('inventory'),
      icon: <AppstoreOutlined />,
      children: [
        { path: '/inventory/branch-matrix', name: t('branchInventory') },
        { path: '/inventory/alerts', name: t('lowStockAlerts') },
        { path: '/inventory/transfers', name: t('stockTransfers') },
        { path: '/inventory/adjustments', name: t('stockAdjustments') },
        { path: '/inventory/movements', name: t('stockMovements') },
      ],
    },
    {
      path: '/reports',
      name: t('reports'),
      icon: <BarChartOutlined />,
    },
    {
      path: '/settings',
      name: t('settings'),
      icon: <SettingOutlined />,
      children: [
        { path: '/settings/warehouses', name: t('warehouses') },
      ],
    },
  ]

  // Filter by backend-provided menu (role-aware)
  const allowedPaths = new Set(backendMenu.map((m) => m.path))
  const menuItems = allMenuItems.filter(
    (item) => !ROLE_GATED_PATHS.has(item.path) || allowedPaths.has(item.path),
  )

  const langItems = [
    {
      key: 'en-US',
      label: 'English',
      onClick: () => i18n.changeLanguage('en-US'),
    },
    {
      key: 'zh-CN',
      label: '中文',
      onClick: () => i18n.changeLanguage('zh-CN'),
    },
  ]

  return (
    <ProLayout
      title="ERP OS"
      logo={null}
      layout="mix"
      menuDataRender={() => menuItems}
      location={{ pathname: location.pathname }}
      menuItemRender={(item, dom) => (
        <span onClick={() => item.path && navigate(item.path)} style={{ cursor: 'pointer' }}>
          {dom}
        </span>
      )}
      actionsRender={() => [
        <Dropdown key="lang" menu={{ items: langItems, selectedKeys: [currentLang] }}>
          <span style={{ cursor: 'pointer', padding: '0 8px', display: 'flex', alignItems: 'center', gap: 4 }}>
            <GlobalOutlined />
            <span style={{ fontSize: 13 }}>{currentLang === 'zh-CN' ? '中文' : 'EN'}</span>
          </span>
        </Dropdown>,
      ]}
      avatarProps={{
        src: null,
        title: user?.full_name ?? user?.email ?? 'User',
        render: (_props, dom) => (
          <Dropdown
            menu={{
              items: [
                {
                  key: 'logout',
                  label: t('logout'),
                  icon: <LogoutOutlined />,
                  onClick: logout,
                },
              ],
            }}
          >
            {dom}
          </Dropdown>
        ),
      }}
    >
      <Outlet />
    </ProLayout>
  )
}

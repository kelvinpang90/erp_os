import {
  AppstoreOutlined,
  BarChartOutlined,
  DashboardOutlined,
  ShoppingCartOutlined,
  ShoppingOutlined,
  SettingOutlined,
  TagsOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import { ProLayout } from '@ant-design/pro-components'
import { Grid } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '../../stores/authStore'
import TopBar from './TopBar'

// Top-level paths that require role-based visibility check.
// Items not in this set are always visible (e.g., Dashboard, SKUs).
// The backend's /api/auth/me menu is the source of truth for visibility:
// if a frontend item's path is in ROLE_GATED_PATHS, it's only shown when the
// backend menu (already role-filtered) contains a node with the same path.
const ROLE_GATED_PATHS = new Set(['/purchase', '/sales', '/inventory', '/reports', '/settings', '/admin'])

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation('menu')
  const backendMenu = useAuthStore((s) => s.menu)
  const screens = Grid.useBreakpoint()
  const isMobile = !screens.lg

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
        { path: '/settings/users', name: t('users') },
        { path: '/settings/currencies', name: t('currencies') },
        { path: '/settings/tax-rates', name: t('taxRates') },
        { path: '/settings/uoms', name: t('uoms') },
        { path: '/settings/brands', name: t('brands') },
        { path: '/settings/categories', name: t('categories') },
        { path: '/settings/ai-features', name: t('aiFeatures') },
      ],
    },
    {
      path: '/admin',
      name: t('admin'),
      icon: <ToolOutlined />,
      children: [
        { path: '/admin/dev-tools', name: t('devTools') },
        { path: '/admin/demo-reset', name: t('demoReset') },
        { path: '/admin/audit-logs', name: t('auditLogs') },
      ],
    },
  ]

  // Filter by backend-provided menu (role-aware)
  const allowedPaths = new Set(backendMenu.map((m) => m.path))
  const menuItems = allMenuItems.filter(
    (item) => !ROLE_GATED_PATHS.has(item.path) || allowedPaths.has(item.path),
  )

  return (
    <ProLayout
      title="ERP OS"
      logo={null}
      layout={isMobile ? 'top' : 'mix'}
      siderWidth={isMobile ? 0 : 208}
      breakpoint="lg"
      defaultCollapsed={isMobile}
      menuDataRender={() => menuItems}
      location={{ pathname: location.pathname }}
      menuItemRender={(item, dom) => (
        <span onClick={() => item.path && navigate(item.path)} style={{ cursor: 'pointer' }}>
          {dom}
        </span>
      )}
      actionsRender={() => [<TopBar key="topbar" />]}
      avatarProps={{ render: () => null }}
      contentStyle={{ padding: isMobile ? 12 : 24 }}
    >
      <Outlet />
    </ProLayout>
  )
}

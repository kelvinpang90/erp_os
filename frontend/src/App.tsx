import { App as AntApp, ConfigProvider } from 'antd'
import enUS from 'antd/locale/en_US'
import zhCN from 'antd/locale/zh_CN'
import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import ErrorBoundary from './components/ErrorBoundary'
import ProtectedRoute from './components/ProtectedRoute'
import { useThemeStore } from './stores/themeStore'
import { lightTheme } from './theme/light'
import { darkTheme } from './theme/dark'

const NotFoundPage = lazy(() => import('./pages/ErrorPages/NotFoundPage'))
const ForbiddenPage = lazy(() => import('./pages/ErrorPages/ForbiddenPage'))

const LoginPage = lazy(() => import('./pages/LoginPage'))
const SKUListPage = lazy(() => import('./pages/SKU/ListPage'))
const SKUDetailPage = lazy(() => import('./pages/SKU/DetailPage'))
const SKUEditPage = lazy(() => import('./pages/SKU/EditPage'))
const SupplierListPage = lazy(() => import('./pages/Purchase/SupplierListPage'))
const SupplierDetailPage = lazy(() => import('./pages/Purchase/SupplierDetailPage'))
const SupplierEditPage = lazy(() => import('./pages/Purchase/SupplierEditPage'))
const CustomerListPage = lazy(() => import('./pages/Sales/CustomerListPage'))
const CustomerDetailPage = lazy(() => import('./pages/Sales/CustomerDetailPage'))
const CustomerEditPage = lazy(() => import('./pages/Sales/CustomerEditPage'))
const WarehouseListPage = lazy(() => import('./pages/Warehouse/WarehouseListPage'))
const WarehouseDetailPage = lazy(() => import('./pages/Warehouse/WarehouseDetailPage'))
const WarehouseEditPage = lazy(() => import('./pages/Warehouse/WarehouseEditPage'))
const POListPage = lazy(() => import('./pages/Purchase/POListPage'))
const PODetailPage = lazy(() => import('./pages/Purchase/PODetailPage'))
const POEditPage = lazy(() => import('./pages/Purchase/POEditPage'))
const OCRUploadPage = lazy(() => import('./pages/Purchase/OCRUploadPage'))
const GRListPage = lazy(() => import('./pages/Purchase/GRListPage'))
const GRCreatePage = lazy(() => import('./pages/Purchase/GRCreatePage'))
const GRDetailPage = lazy(() => import('./pages/Purchase/GRDetailPage'))
const SOListPage = lazy(() => import('./pages/Sales/SOListPage'))
const SODetailPage = lazy(() => import('./pages/Sales/SODetailPage'))
const SOEditPage = lazy(() => import('./pages/Sales/SOEditPage'))
const DOListPage = lazy(() => import('./pages/Sales/DOListPage'))
const DOCreatePage = lazy(() => import('./pages/Sales/DOCreatePage'))
const DODetailPage = lazy(() => import('./pages/Sales/DODetailPage'))
const InvoiceListPage = lazy(() => import('./pages/EInvoice/InvoiceListPage'))
const InvoiceDetailPage = lazy(() => import('./pages/EInvoice/InvoiceDetailPage'))
const CreditNoteListPage = lazy(() => import('./pages/Sales/CreditNote/CreditNoteListPage'))
const CreditNoteDetailPage = lazy(() => import('./pages/Sales/CreditNote/CreditNoteDetailPage'))
const CreditNoteCreatePage = lazy(() => import('./pages/Sales/CreditNote/CreditNoteCreatePage'))
const TransferListPage = lazy(() => import('./pages/Inventory/TransferListPage'))
const TransferDetailPage = lazy(() => import('./pages/Inventory/TransferDetailPage'))
const TransferCreatePage = lazy(() => import('./pages/Inventory/TransferCreatePage'))
const TransferEditPage = lazy(() => import('./pages/Inventory/TransferEditPage'))
const TransferReceivePage = lazy(() => import('./pages/Inventory/TransferReceivePage'))
const AdjustmentListPage = lazy(() => import('./pages/Inventory/AdjustmentListPage'))
const AdjustmentCreatePage = lazy(() => import('./pages/Inventory/AdjustmentCreatePage'))
const AdjustmentDetailPage = lazy(() => import('./pages/Inventory/AdjustmentDetailPage'))
const MovementListPage = lazy(() => import('./pages/Inventory/MovementListPage'))
const BranchInventoryPage = lazy(() => import('./pages/Inventory/BranchInventoryPage'))
const AlertPage = lazy(() => import('./pages/Inventory/AlertPage'))
const DashboardPage = lazy(() => import('./pages/Dashboard'))
const ReportsPage = lazy(() => import('./pages/Reports'))
const SettingsHubPage = lazy(() => import('./pages/Settings'))
const CurrenciesListPage = lazy(() => import('./pages/Settings/CurrenciesListPage'))
const TaxRatesListPage = lazy(() => import('./pages/Settings/TaxRatesListPage'))
const UOMsListPage = lazy(() => import('./pages/Settings/UOMsListPage'))
const BrandsListPage = lazy(() => import('./pages/Settings/BrandsListPage'))
const CategoriesListPage = lazy(() => import('./pages/Settings/CategoriesListPage'))
const UserListPage = lazy(() => import('./pages/Settings/Users/UserListPage'))
const UserEditPage = lazy(() => import('./pages/Settings/Users/UserEditPage'))
const UserDetailPage = lazy(() => import('./pages/Settings/Users/UserDetailPage'))
const AIFeaturesPage = lazy(() => import('./pages/Settings/AIFeaturesPage'))
const DevToolsPage = lazy(() => import('./pages/Admin/DevToolsPage'))
const DemoResetPage = lazy(() => import('./pages/Admin/DemoResetPage'))
const AuditLogsPage = lazy(() => import('./pages/Admin/AuditLogsPage'))

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/skus" element={<SKUListPage />} />
        <Route path="/skus/create" element={<SKUEditPage />} />
        <Route path="/skus/:id" element={<SKUDetailPage />} />
        <Route path="/skus/:id/edit" element={<SKUEditPage />} />
        <Route path="/purchase/orders" element={<POListPage />} />
        <Route path="/purchase/orders/ocr-upload" element={<OCRUploadPage />} />
        <Route path="/purchase/orders/create" element={<POEditPage />} />
        <Route path="/purchase/orders/:id" element={<PODetailPage />} />
        <Route path="/purchase/orders/:id/edit" element={<POEditPage />} />
        <Route path="/purchase/goods-receipts" element={<GRListPage />} />
        <Route path="/purchase/goods-receipts/create" element={<GRCreatePage />} />
        <Route path="/purchase/goods-receipts/:id" element={<GRDetailPage />} />
        <Route path="/purchase/suppliers" element={<SupplierListPage />} />
        <Route path="/purchase/suppliers/create" element={<SupplierEditPage />} />
        <Route path="/purchase/suppliers/:id" element={<SupplierDetailPage />} />
        <Route path="/purchase/suppliers/:id/edit" element={<SupplierEditPage />} />
        <Route path="/sales/customers" element={<CustomerListPage />} />
        <Route path="/sales/customers/create" element={<CustomerEditPage />} />
        <Route path="/sales/customers/:id" element={<CustomerDetailPage />} />
        <Route path="/sales/customers/:id/edit" element={<CustomerEditPage />} />
        <Route path="/sales/orders" element={<SOListPage />} />
        <Route path="/sales/orders/create" element={<SOEditPage />} />
        <Route path="/sales/orders/:id" element={<SODetailPage />} />
        <Route path="/sales/orders/:id/edit" element={<SOEditPage />} />
        <Route path="/sales/delivery" element={<DOListPage />} />
        <Route path="/sales/delivery/create" element={<DOCreatePage />} />
        <Route path="/sales/delivery/:id" element={<DODetailPage />} />
        <Route path="/sales/einvoice" element={<InvoiceListPage />} />
        <Route path="/sales/einvoice/:id" element={<InvoiceDetailPage />} />
        <Route path="/sales/credit-notes" element={<CreditNoteListPage />} />
        <Route path="/sales/credit-notes/new" element={<CreditNoteCreatePage />} />
        <Route path="/sales/credit-notes/:id" element={<CreditNoteDetailPage />} />
        <Route path="/inventory/transfers" element={<TransferListPage />} />
        <Route path="/inventory/transfers/new" element={<TransferCreatePage />} />
        <Route path="/inventory/transfers/:id" element={<TransferDetailPage />} />
        <Route path="/inventory/transfers/:id/edit" element={<TransferEditPage />} />
        <Route path="/inventory/transfers/:id/receive" element={<TransferReceivePage />} />
        <Route path="/inventory/adjustments" element={<AdjustmentListPage />} />
        <Route path="/inventory/adjustments/new" element={<AdjustmentCreatePage />} />
        <Route path="/inventory/adjustments/:id" element={<AdjustmentDetailPage />} />
        <Route path="/inventory/movements" element={<MovementListPage />} />
        <Route path="/inventory/branch-matrix" element={<BranchInventoryPage />} />
        <Route path="/inventory/alerts" element={<AlertPage />} />
        <Route path="/settings" element={<SettingsHubPage />} />
        <Route path="/settings/currencies" element={<CurrenciesListPage />} />
        <Route path="/settings/tax-rates" element={<TaxRatesListPage />} />
        <Route path="/settings/uoms" element={<UOMsListPage />} />
        <Route path="/settings/brands" element={<BrandsListPage />} />
        <Route path="/settings/categories" element={<CategoriesListPage />} />
        <Route path="/settings/users" element={<UserListPage />} />
        <Route path="/settings/users/create" element={<UserEditPage />} />
        <Route path="/settings/users/:id" element={<UserDetailPage />} />
        <Route path="/settings/users/:id/edit" element={<UserEditPage />} />
        <Route path="/settings/warehouses" element={<WarehouseListPage />} />
        <Route path="/settings/warehouses/create" element={<WarehouseEditPage />} />
        <Route path="/settings/warehouses/:id" element={<WarehouseDetailPage />} />
        <Route path="/settings/warehouses/:id/edit" element={<WarehouseEditPage />} />
        <Route path="/settings/ai" element={<AIFeaturesPage />} />
        <Route path="/settings/ai-features" element={<AIFeaturesPage />} />
        <Route path="/admin/dev-tools" element={<DevToolsPage />} />
        <Route path="/admin/demo-reset" element={<DemoResetPage />} />
        <Route path="/admin/audit-logs" element={<AuditLogsPage />} />
        <Route path="/403" element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  const mode = useThemeStore((s) => s.mode)
  const { i18n } = useTranslation()
  const antdLocale = i18n.language?.startsWith('zh') ? zhCN : enUS
  return (
    <ConfigProvider theme={mode === 'dark' ? darkTheme : lightTheme} locale={antdLocale}>
      <AntApp>
        <ErrorBoundary>
          <BrowserRouter>
            <Suspense fallback={<div style={{ padding: 40 }}>Loading...</div>}>
              <AppRoutes />
            </Suspense>
          </BrowserRouter>
        </ErrorBoundary>
      </AntApp>
    </ConfigProvider>
  )
}

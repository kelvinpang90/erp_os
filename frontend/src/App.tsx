import { App as AntApp, ConfigProvider } from 'antd'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'

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

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div style={{ padding: 24, textAlign: 'center' }}>
      <h2>{title}</h2>
      <p style={{ color: '#888' }}>Coming soon...</p>
    </div>
  )
}

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
        <Route index element={<PlaceholderPage title="Dashboard" />} />
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
        <Route path="/settings/warehouses" element={<WarehouseListPage />} />
        <Route path="/settings/warehouses/create" element={<WarehouseEditPage />} />
        <Route path="/settings/warehouses/:id" element={<WarehouseDetailPage />} />
        <Route path="/settings/warehouses/:id/edit" element={<WarehouseEditPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <ConfigProvider theme={{ token: { colorPrimary: '#1677ff' } }}>
      <AntApp>
        <BrowserRouter>
          <Suspense fallback={<div style={{ padding: 40 }}>Loading...</div>}>
            <AppRoutes />
          </Suspense>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  )
}

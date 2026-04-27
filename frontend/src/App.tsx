import { App as AntApp, ConfigProvider } from 'antd'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const SKUListPage = lazy(() => import('./pages/SKU/ListPage'))
const SKUDetailPage = lazy(() => import('./pages/SKU/DetailPage'))
const SKUEditPage = lazy(() => import('./pages/SKU/EditPage'))

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

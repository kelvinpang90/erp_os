import { BrowserRouter, Route, Routes } from 'react-router-dom'

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', flexDirection: 'column', fontFamily: 'sans-serif' }}>
      <h1 style={{ fontSize: 32, marginBottom: 8 }}>ERP OS</h1>
      <p style={{ color: '#666' }}>{title} — coming in Window 03+</p>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<PlaceholderPage title="Login" />} />
        <Route path="/*" element={<PlaceholderPage title="Dashboard" />} />
      </Routes>
    </BrowserRouter>
  )
}

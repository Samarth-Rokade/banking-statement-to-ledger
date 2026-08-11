import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import AuthGuard from './components/layout/AuthGuard'
import DashboardPage from './pages/Dashboard/DashboardPage'
import LoginPage from './pages/Login/LoginPage'
import ProcessingStatusPage from './pages/ProcessingStatus/ProcessingStatusPage'
import RegisterPage from './pages/Register/RegisterPage'
import UploadStatementPage from './pages/UploadStatement/UploadStatementPage'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/dashboard"
            element={
              <AuthGuard>
                <DashboardPage />
              </AuthGuard>
            }
          />
          <Route
            path="/upload"
            element={
              <AuthGuard>
                <UploadStatementPage />
              </AuthGuard>
            }
          />
          <Route
            path="/jobs/:jobId"
            element={
              <AuthGuard>
                <ProcessingStatusPage />
              </AuthGuard>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </QueryClientProvider>
  )
}

export default App

import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './auth';
import ErrorBoundary from './components/ErrorBoundary';
import BottomNav from './components/BottomNav';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import BriefListPage from './pages/BriefListPage';
import BriefDetailPage from './pages/BriefDetailPage';
import UploadPage from './pages/UploadPage';
import QuickScanPage from './pages/QuickScanPage';
import TagsPage from './pages/TagsPage';
import PapierkorbPage from './pages/PapierkorbPage';
import BulkUploadPage from './pages/BulkUploadPage';
import KorrespondentenPage from './pages/KorrespondentenPage';
import AccountsPage from './pages/AccountsPage';
import VoiceMemoPage from './pages/VoiceMemoPage';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="loading-screen">Laden...</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="loading-screen">Laden...</div>;
  }

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
        <Route path="/register" element={user ? <Navigate to="/" replace /> : <RegisterPage />} />
        <Route path="/" element={<RequireAuth><DashboardPage /></RequireAuth>} />
        <Route path="/briefe" element={<RequireAuth><BriefListPage /></RequireAuth>} />
        <Route path="/briefe/:id" element={<RequireAuth><BriefDetailPage /></RequireAuth>} />
        <Route path="/upload" element={<RequireAuth><UploadPage /></RequireAuth>} />
        <Route path="/scan" element={<RequireAuth><QuickScanPage /></RequireAuth>} />
        <Route path="/tags" element={<RequireAuth><TagsPage /></RequireAuth>} />
        <Route path="/papierkorb" element={<RequireAuth><PapierkorbPage /></RequireAuth>} />
        <Route path="/bulk" element={<RequireAuth><BulkUploadPage /></RequireAuth>} />
        <Route path="/korrespondenten" element={<RequireAuth><KorrespondentenPage /></RequireAuth>} />
        <Route path="/konten" element={<RequireAuth><AccountsPage /></RequireAuth>} />
        <Route path="/voice" element={<RequireAuth><VoiceMemoPage /></RequireAuth>} />
      </Routes>
      {user && <BottomNav />}
    </ErrorBoundary>
  );
}

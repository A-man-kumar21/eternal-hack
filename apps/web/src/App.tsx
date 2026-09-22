import type { ReactNode } from 'react';
import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import Nav from './components/Nav';
import { Spinner } from './components/ui';
import { useAuth } from './auth/AuthContext';
import Login from './pages/Login';
import Cases from './pages/Cases';
import CaseWorkspace from './pages/CaseWorkspace';
import Timeline from './pages/Timeline';
import RedactionReview from './pages/RedactionReview';
import AuditorConsole from './pages/AuditorConsole';
import ExportPage from './pages/Export';

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="page">
        <Spinner label="Restoring session…" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function Shell() {
  return (
    <div className="app-shell">
      <Nav />
      <main>
        <Outlet />
      </main>
      <footer className="footer-note">
        e-Abhilekh · hackathon prototype · all accounts & data are fictional demo content
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><Shell /></RequireAuth>}>
        <Route path="/" element={<Navigate to="/cases" replace />} />
        <Route path="/cases" element={<Cases />} />
        <Route path="/cases/:id" element={<CaseWorkspace />} />
        <Route path="/cases/:id/timeline" element={<Timeline />} />
        <Route path="/cases/:id/redact/:docId" element={<RedactionReview />} />
        <Route path="/cases/:id/export" element={<ExportPage />} />
        <Route path="/auditor" element={<AuditorConsole />} />
      </Route>
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  );
}

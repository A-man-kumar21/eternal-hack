import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'motion/react';
import Nav from './components/Nav';
import { Spinner } from './components/ui';
import { useAuth } from './auth/AuthContext';
import Login from './pages/Login';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
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

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  }, [pathname]);
  return null;
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

/** Routes keyed by pathname inside AnimatePresence — every page transition
 *  cross-fades with a soft vertical drift via the <Page> wrapper each page uses. */
function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route element={<RequireAuth><Shell /></RequireAuth>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/cases" element={<Cases />} />
          <Route path="/cases/:id" element={<CaseWorkspace />} />
          <Route path="/cases/:id/timeline" element={<Timeline />} />
          <Route path="/cases/:id/redact/:docId" element={<RedactionReview />} />
          <Route path="/cases/:id/export" element={<ExportPage />} />
          <Route path="/auditor" element={<AuditorConsole />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  );
}

import { useEffect, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";

import {
  createReport,
  deleteReport,
  getCurrentUser,
  listReports,
  logout,
  updateReport,
} from "./api";

import Login from "./components/Login";
import Home from "./pages/Home";
import CreateRecord from "./pages/CreateRecord";
import UpdateRecord from "./pages/UpdateRecord";
import DeleteRecord from "./pages/DeleteRecord";


function RequireAuth({ user, children }) {
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}


export default function App() {
  const navigate = useNavigate();

  const [user, setUser] = useState(null);
  const [reports, setReports] = useState([]);
  const [authLoading, setAuthLoading] = useState(true);
  const [reportsLoading, setReportsLoading] = useState(false);

  useEffect(() => {
    async function restoreSession() {
      try {
        const result = await getCurrentUser();
        setUser(result.user);
      } catch {
        setUser(null);
      } finally {
        setAuthLoading(false);
      }
    }

    restoreSession();
  }, []);

  useEffect(() => {
    async function loadReports() {
      if (!user) {
        setReports([]);
        return;
      }

      setReportsLoading(true);

      try {
        const data = await listReports();
        setReports(data);
      } catch (requestError) {
        if (requestError.response?.status === 401) {
          setUser(null);
          navigate("/login");
        }
      } finally {
        setReportsLoading(false);
      }
    }

    loadReports();
  }, [user, navigate]);

  async function handleLogin(loggedInUser) {
    setUser(loggedInUser);
    navigate("/");
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setReports([]);
    navigate("/login");
  }

  async function handleCreate(payload) {
    const created = await createReport(payload);
    setReports((previous) => [...previous, created]);
    navigate("/");
  }

  async function handleUpdate(id, payload) {
    const updated = await updateReport(id, payload);

    setReports((previous) =>
      previous.map((report) =>
        report.id === Number(id) ? updated : report,
      ),
    );

    navigate("/");
  }

  function handleDeleted(id) {
    setReports((previous) =>
      previous.filter((report) => report.id !== id),
    );
  }

  if (authLoading) {
    return <main className="app-shell">Checking login session...</main>;
  }

  return (
    <main className="app-shell">
      <header className="site-header">
        <div>
          <h1>Package Vulnerability Reports</h1>
          <p className="muted">
            DATA 260 Homework 4
          </p>
        </div>

        {user && (
          <div className="user-badge">
            Signed in as {user.email}
          </div>
        )}
      </header>

      <Routes>
        <Route
          path="/login"
          element={
            user ? (
              <Navigate to="/" replace />
            ) : (
              <Login onLoggedIn={handleLogin} />
            )
          }
        />

        <Route
          path="/"
          element={
            <Home
              user={user}
              reports={reports}
              loading={reportsLoading}
              onLogout={handleLogout}
            />
          }
        />

        <Route
          path="/create"
          element={
            <RequireAuth user={user}>
              <CreateRecord onCreate={handleCreate} />
            </RequireAuth>
          }
        />

        <Route
          path="/update/:id"
          element={
            <RequireAuth user={user}>
              <UpdateRecord onUpdate={handleUpdate} />
            </RequireAuth>
          }
        />

        <Route
          path="/delete/:id"
          element={
            <RequireAuth user={user}>
              <DeleteRecord onDeleted={handleDeleted} />
            </RequireAuth>
          }
        />
      </Routes>
    </main>
  );
}

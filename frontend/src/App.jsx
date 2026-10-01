import { useEffect, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";

import {
  clearReports,
  addReport,
  editReport,
  fetchReports,
  removeReport,
} from "./features/reports/reportsSlice";

import {
  getCurrentUser,
  logout,
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
  const dispatch = useDispatch();

  const reports = useSelector(
    (state) => state.reports.items,
  );

  const reportsStatus = useSelector(
    (state) => state.reports.status,
  );

  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

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
    if (!user) {
      dispatch(clearReports());
      return;
    }

    dispatch(fetchReports())
      .unwrap()
      .catch((error) => {
        if (String(error).toLowerCase().includes("401")) {
          setUser(null);
          navigate("/login");
        }
      });
  }, [dispatch, navigate, user]);

  async function handleLogin(loggedInUser) {
    setUser(loggedInUser);
    navigate("/");
  }

  async function handleLogout() {
    await logout();
    dispatch(clearReports());
    setUser(null);
    navigate("/login");
  }

  async function handleCreate(payload) {
    await dispatch(addReport(payload)).unwrap();
    navigate("/");
  }

  async function handleUpdate(id, payload) {
    await dispatch(
      editReport({
        id,
        payload,
      }),
    ).unwrap();

    navigate("/");
  }

  async function handleDeleted(id) {
    await dispatch(removeReport(id)).unwrap();
    navigate("/");
  }

  if (authLoading) {
    return (
      <main className="app-shell">
        Checking login session...
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="site-header">
        <div>
          <h1>Package Vulnerability Reports</h1>
          <p className="muted">
            DATA 260 Homework 5
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
              loading={reportsStatus === "loading"}
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
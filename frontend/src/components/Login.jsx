import { useState } from "react";
import { login } from "../api";

export default function Login({ onLoggedIn }) {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("password");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);

    try {
      // The backend sets the HTTP-only session cookie.
      const result = await login(email, password);
      onLoggedIn(result.user);
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      setError(detail || "Login failed. Check your email and password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Login</h2>
      <p className="muted">
        Sign in to manage open-source package vulnerability reports.
      </p>

      <form onSubmit={handleSubmit} className="form">
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        {error && <p className="error">{error}</p>}

        <button type="submit" disabled={busy}>
          {busy ? "Logging in..." : "Login"}
        </button>
      </form>
    </section>
  );
}

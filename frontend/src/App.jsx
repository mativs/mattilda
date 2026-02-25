import { useEffect, useMemo, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:18000";
const TOKEN_KEY = "mattilda_token";

export default function App() {
  const [loadingPublic, setLoadingPublic] = useState(true);
  const [loadingAuth, setLoadingAuth] = useState(false);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);
  const [me, setMe] = useState(null);
  const [username, setUsername] = useState("admin@example.com");
  const [password, setPassword] = useState("admin123");
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch(`${API_URL}/api/v1/ping`);
        if (!response.ok) {
          throw new Error(`Request failed with ${response.status}`);
        }
        const data = await response.json();
        setPayload(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoadingPublic(false);
      }
    }

    load();
  }, []);

  const isAuthenticated = useMemo(() => Boolean(token), [token]);

  useEffect(() => {
    async function loadMe() {
      if (!token) {
        setMe(null);
        return;
      }
      setLoadingAuth(true);
      try {
        const response = await fetch(`${API_URL}/api/v1/users/me`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        if (!response.ok) {
          throw new Error("Session expired or invalid token");
        }
        setMe(await response.json());
      } catch (err) {
        setError(err.message);
        localStorage.removeItem(TOKEN_KEY);
        setToken("");
      } finally {
        setLoadingAuth(false);
      }
    }

    loadMe();
  }, [token]);

  async function onLogin(event) {
    event.preventDefault();
    setError("");
    setLoadingAuth(true);
    try {
      const body = new URLSearchParams({
        username,
        password
      });
      const response = await fetch(`${API_URL}/api/v1/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body
      });
      if (!response.ok) {
        throw new Error("Invalid credentials");
      }
      const data = await response.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingAuth(false);
    }
  }

  function onLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setMe(null);
  }

  return (
    <main className="container">
      <h1>Mattilda Take-Home</h1>
      <p>Frontend connected to FastAPI backend with JWT auth.</p>
      {loadingPublic && <p>Loading backend status...</p>}
      {error && <p className="error">Error: {error}</p>}
      {payload && (
        <div className="card">
          <p>
            <strong>Message:</strong> {payload.message}
          </p>
          <p>
            <strong>DB:</strong> {String(payload.db_connected)}
          </p>
          <p>
            <strong>Redis:</strong> {String(payload.redis_connected)}
          </p>
        </div>
      )}

      {!isAuthenticated && (
        <form className="card form" onSubmit={onLogin}>
          <h2>Login</h2>
          <label>
            Email
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <button disabled={loadingAuth} type="submit">
            {loadingAuth ? "Signing in..." : "Sign in"}
          </button>
        </form>
      )}

      {isAuthenticated && (
        <section className="card">
          <h2>Home</h2>
          {loadingAuth && <p>Loading session...</p>}
          {me && (
            <>
              <p>
                <strong>User:</strong> {me.email}
              </p>
              <p>
                <strong>Roles:</strong> {me.roles.join(", ")}
              </p>
              <p>
                <strong>Name:</strong> {me.profile.first_name} {me.profile.last_name}
              </p>
            </>
          )}
          <button onClick={onLogout} type="button">
            Logout
          </button>
        </section>
      )}
    </main>
  );
}

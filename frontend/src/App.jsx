import { useEffect, useMemo, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:18000";
const TOKEN_KEY = "mattilda_token";
const SCHOOL_KEY = "mattilda_school_id";

export default function App() {
  const [loadingPublic, setLoadingPublic] = useState(true);
  const [loadingAuth, setLoadingAuth] = useState(false);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);
  const [me, setMe] = useState(null);
  const [activeSchool, setActiveSchool] = useState(null);
  const [username, setUsername] = useState("admin@example.com");
  const [password, setPassword] = useState("admin123");
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [selectedSchoolId, setSelectedSchoolId] = useState(() => localStorage.getItem(SCHOOL_KEY) ?? "");

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
  const selectedSchool = useMemo(() => {
    if (!me || !selectedSchoolId) {
      return null;
    }
    return me.schools.find((school) => String(school.school_id) === String(selectedSchoolId)) ?? null;
  }, [me, selectedSchoolId]);

  useEffect(() => {
    async function loadMe() {
      if (!token) {
        setMe(null);
        setActiveSchool(null);
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
        const mePayload = await response.json();
        setMe(mePayload);
        if (mePayload.schools.length === 0) {
          setSelectedSchoolId("");
          localStorage.removeItem(SCHOOL_KEY);
          return;
        }
        const selectedExists = mePayload.schools.some(
          (school) => String(school.school_id) === String(selectedSchoolId)
        );
        if (!selectedExists) {
          const defaultSchoolId = String(mePayload.schools[0].school_id);
          setSelectedSchoolId(defaultSchoolId);
          localStorage.setItem(SCHOOL_KEY, defaultSchoolId);
        }
      } catch (err) {
        setError(err.message);
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(SCHOOL_KEY);
        setToken("");
        setSelectedSchoolId("");
      } finally {
        setLoadingAuth(false);
      }
    }

    loadMe();
  }, [token]);

  useEffect(() => {
    async function loadActiveSchool() {
      if (!token || !selectedSchoolId) {
        setActiveSchool(null);
        return;
      }
      try {
        const response = await fetch(`${API_URL}/api/v1/schools/${selectedSchoolId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            "X-School-Id": String(selectedSchoolId)
          }
        });
        if (!response.ok) {
          throw new Error("Unable to load selected school");
        }
        setActiveSchool(await response.json());
      } catch (err) {
        setError(err.message);
        setActiveSchool(null);
      }
    }

    loadActiveSchool();
  }, [token, selectedSchoolId]);

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
    localStorage.removeItem(SCHOOL_KEY);
    setToken("");
    setSelectedSchoolId("");
    setMe(null);
    setActiveSchool(null);
  }

  function onSchoolChange(event) {
    const nextSchoolId = event.target.value;
    setSelectedSchoolId(nextSchoolId);
    if (nextSchoolId) {
      localStorage.setItem(SCHOOL_KEY, nextSchoolId);
      return;
    }
    localStorage.removeItem(SCHOOL_KEY);
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
                <strong>Name:</strong> {me.profile.first_name} {me.profile.last_name}
              </p>
              {me.schools.length > 0 && (
                <>
                  <label>
                    Active School
                    <select value={selectedSchoolId} onChange={onSchoolChange}>
                      {me.schools.map((school) => (
                        <option key={school.school_id} value={school.school_id}>
                          {school.school_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedSchool && (
                    <p>
                      <strong>Roles in school:</strong> {selectedSchool.roles.join(", ")}
                    </p>
                  )}
                  {activeSchool && (
                    <p>
                      <strong>Selected school:</strong> {activeSchool.name}
                    </p>
                  )}
                </>
              )}
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

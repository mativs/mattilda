import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);

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
        setLoading(false);
      }
    }

    load();
  }, []);

  return (
    <main className="container">
      <h1>Mattilda Take-Home</h1>
      <p>Frontend connected to FastAPI backend.</p>
      {loading && <p>Loading backend status...</p>}
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
    </main>
  );
}

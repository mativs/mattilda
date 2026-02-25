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
  const [students, setStudents] = useState([]);
  const [users, setUsers] = useState([]);
  const [adminMessage, setAdminMessage] = useState("");
  const [newUser, setNewUser] = useState({ email: "", password: "", first_name: "", last_name: "", role: "admin" });
  const [newSchool, setNewSchool] = useState({ name: "", slug: "" });
  const [newStudent, setNewStudent] = useState({ first_name: "", last_name: "", external_id: "", user_id: "" });
  const [linkUserSchool, setLinkUserSchool] = useState({ user_id: "", role: "teacher" });
  const [linkUserStudent, setLinkUserStudent] = useState({ user_id: "", student_id: "" });
  const [linkStudentSchool, setLinkStudentSchool] = useState({ student_id: "" });
  const [updateUser, setUpdateUser] = useState({ user_id: "", email: "", password: "", first_name: "", last_name: "", is_active: "true" });
  const [updateSchool, setUpdateSchool] = useState({ school_id: "", name: "", slug: "", is_active: "true" });
  const [updateStudent, setUpdateStudent] = useState({ student_id: "", first_name: "", last_name: "", external_id: "" });
  const [deleteIds, setDeleteIds] = useState({ user_id: "", school_id: "", student_id: "" });

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
  const isSchoolAdmin = useMemo(() => {
    if (!selectedSchool) {
      return false;
    }
    return selectedSchool.roles.includes("admin");
  }, [selectedSchool]);
  const studentsForSelectedSchool = useMemo(() => {
    if (!me || !selectedSchoolId) {
      return [];
    }
    return (me.students ?? []).filter((student) => student.school_ids.includes(Number(selectedSchoolId)));
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

  async function authenticatedRequest(path, options = {}) {
    if (!token) {
      throw new Error("Missing auth token");
    }
    const headers = {
      Authorization: `Bearer ${token}`,
      ...(options.headers ?? {})
    };
    if (selectedSchoolId) {
      headers["X-School-Id"] = String(selectedSchoolId);
    }
    const response = await fetch(`${API_URL}${path}`, { ...options, headers });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Request failed with ${response.status}`);
    }
    if (response.status === 204) {
      return null;
    }
    return response.json();
  }

  async function refreshAdminData() {
    if (!isSchoolAdmin || !selectedSchoolId) {
      setStudents([]);
      setUsers([]);
      return;
    }
    try {
      const [studentsPayload, usersPayload] = await Promise.all([
        authenticatedRequest("/api/v1/students"),
        authenticatedRequest("/api/v1/users")
      ]);
      setStudents(studentsPayload);
      setUsers(usersPayload);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refreshAdminData();
  }, [isSchoolAdmin, selectedSchoolId, token]);

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

  async function handleCreateUser(event) {
    event.preventDefault();
    setAdminMessage("");
    try {
      const createdUser = await authenticatedRequest("/api/v1/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: newUser.email,
          password: newUser.password,
          is_active: true,
          profile: {
            first_name: newUser.first_name,
            last_name: newUser.last_name
          }
        })
      });
      await authenticatedRequest(`/api/v1/schools/${selectedSchoolId}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: createdUser.id,
          role: newUser.role
        })
      });
      setNewUser({ email: "", password: "", first_name: "", last_name: "", role: "admin" });
      setAdminMessage("User created and associated to school");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreateSchool(event) {
    event.preventDefault();
    setAdminMessage("");
    try {
      await authenticatedRequest("/api/v1/schools", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newSchool)
      });
      setNewSchool({ name: "", slug: "" });
      setAdminMessage("School created");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreateStudent(event) {
    event.preventDefault();
    setAdminMessage("");
    try {
      const student = await authenticatedRequest("/api/v1/students", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: newStudent.first_name,
          last_name: newStudent.last_name,
          external_id: newStudent.external_id || null
        })
      });
      await authenticatedRequest(`/api/v1/students/${student.id}/schools`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ school_id: Number(selectedSchoolId) })
      });
      if (newStudent.user_id) {
        await authenticatedRequest(`/api/v1/students/${student.id}/users`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: Number(newStudent.user_id) })
        });
      }
      setNewStudent({ first_name: "", last_name: "", external_id: "", user_id: "" });
      setAdminMessage("Student created and associated");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleLinkUserSchool(event) {
    event.preventDefault();
    setAdminMessage("");
    try {
      await authenticatedRequest(`/api/v1/schools/${selectedSchoolId}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: Number(linkUserSchool.user_id), role: linkUserSchool.role })
      });
      setAdminMessage("User linked to school");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleLinkUserStudent(event) {
    event.preventDefault();
    setAdminMessage("");
    try {
      await authenticatedRequest(`/api/v1/students/${Number(linkUserStudent.student_id)}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: Number(linkUserStudent.user_id) })
      });
      setAdminMessage("User linked to student");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleLinkStudentSchool(event) {
    event.preventDefault();
    setAdminMessage("");
    try {
      await authenticatedRequest(`/api/v1/students/${Number(linkStudentSchool.student_id)}/schools`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ school_id: Number(selectedSchoolId) })
      });
      setAdminMessage("Student linked to school");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleUpdateUser(event) {
    event.preventDefault();
    try {
      await authenticatedRequest(`/api/v1/users/${Number(updateUser.user_id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: updateUser.email || undefined,
          password: updateUser.password || undefined,
          is_active: updateUser.is_active === "true",
          profile: {
            first_name: updateUser.first_name || undefined,
            last_name: updateUser.last_name || undefined
          }
        })
      });
      setAdminMessage("User updated");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleUpdateSchool(event) {
    event.preventDefault();
    try {
      await authenticatedRequest(`/api/v1/schools/${Number(updateSchool.school_id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-School-Id": String(updateSchool.school_id) },
        body: JSON.stringify({
          name: updateSchool.name || undefined,
          slug: updateSchool.slug || undefined,
          is_active: updateSchool.is_active === "true"
        })
      });
      setAdminMessage("School updated");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleUpdateStudent(event) {
    event.preventDefault();
    try {
      await authenticatedRequest(`/api/v1/students/${Number(updateStudent.student_id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: updateStudent.first_name || undefined,
          last_name: updateStudent.last_name || undefined,
          external_id: updateStudent.external_id || undefined
        })
      });
      setAdminMessage("Student updated");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteUser(event) {
    event.preventDefault();
    try {
      await authenticatedRequest(`/api/v1/users/${Number(deleteIds.user_id)}`, { method: "DELETE" });
      setAdminMessage("User deleted");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteSchool(event) {
    event.preventDefault();
    try {
      await authenticatedRequest(`/api/v1/schools/${Number(deleteIds.school_id)}`, {
        method: "DELETE",
        headers: { "X-School-Id": String(deleteIds.school_id) }
      });
      setAdminMessage("School deleted");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteStudent(event) {
    event.preventDefault();
    try {
      await authenticatedRequest(`/api/v1/students/${Number(deleteIds.student_id)}`, { method: "DELETE" });
      setAdminMessage("Student deleted");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeassociateUserSchool(event) {
    event.preventDefault();
    try {
      await authenticatedRequest(`/api/v1/schools/${selectedSchoolId}/users/${Number(linkUserSchool.user_id)}`, { method: "DELETE" });
      setAdminMessage("User deassociated from school");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeassociateUserStudent(event) {
    event.preventDefault();
    try {
      await authenticatedRequest(`/api/v1/students/${Number(linkUserStudent.student_id)}/users/${Number(linkUserStudent.user_id)}`, { method: "DELETE" });
      setAdminMessage("User deassociated from student");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeassociateStudentSchool(event) {
    event.preventDefault();
    try {
      await authenticatedRequest(`/api/v1/students/${Number(linkStudentSchool.student_id)}/schools/${Number(selectedSchoolId)}`, { method: "DELETE" });
      setAdminMessage("Student deassociated from school");
      await refreshAdminData();
    } catch (err) {
      setError(err.message);
    }
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
                  <div>
                    <strong>My students in this school:</strong>
                    {studentsForSelectedSchool.length === 0 ? (
                      <p>None assigned.</p>
                    ) : (
                      <ul>
                        {studentsForSelectedSchool.map((student) => (
                          <li key={student.id}>
                            {student.first_name} {student.last_name}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </>
              )}
            </>
          )}
          {isSchoolAdmin && (
            <section className="card">
              <h3>Admin Section</h3>
              {adminMessage && <p>{adminMessage}</p>}
              <form className="form" onSubmit={handleCreateUser}>
                <h4>Create User</h4>
                <input placeholder="email" value={newUser.email} onChange={(event) => setNewUser({ ...newUser, email: event.target.value })} />
                <input type="password" placeholder="password" value={newUser.password} onChange={(event) => setNewUser({ ...newUser, password: event.target.value })} />
                <input placeholder="first name" value={newUser.first_name} onChange={(event) => setNewUser({ ...newUser, first_name: event.target.value })} />
                <input placeholder="last name" value={newUser.last_name} onChange={(event) => setNewUser({ ...newUser, last_name: event.target.value })} />
                <select value={newUser.role} onChange={(event) => setNewUser({ ...newUser, role: event.target.value })}>
                  <option value="admin">admin</option>
                  <option value="director">director</option>
                  <option value="teacher">teacher</option>
                  <option value="student">student</option>
                  <option value="parent">parent</option>
                </select>
                <button type="submit">Create user</button>
              </form>
              <form className="form" onSubmit={handleCreateSchool}>
                <h4>Create School</h4>
                <input placeholder="name" value={newSchool.name} onChange={(event) => setNewSchool({ ...newSchool, name: event.target.value })} />
                <input placeholder="slug" value={newSchool.slug} onChange={(event) => setNewSchool({ ...newSchool, slug: event.target.value })} />
                <button type="submit">Create school</button>
              </form>
              <form className="form" onSubmit={handleCreateStudent}>
                <h4>Create Student</h4>
                <input placeholder="first name" value={newStudent.first_name} onChange={(event) => setNewStudent({ ...newStudent, first_name: event.target.value })} />
                <input placeholder="last name" value={newStudent.last_name} onChange={(event) => setNewStudent({ ...newStudent, last_name: event.target.value })} />
                <input placeholder="external id" value={newStudent.external_id} onChange={(event) => setNewStudent({ ...newStudent, external_id: event.target.value })} />
                <select value={newStudent.user_id} onChange={(event) => setNewStudent({ ...newStudent, user_id: event.target.value })}>
                  <option value="">optional user</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.id} - {user.email}
                    </option>
                  ))}
                </select>
                <button type="submit">Create student</button>
              </form>
              <form className="form" onSubmit={handleLinkUserSchool}>
                <h4>Associate User with School</h4>
                <select value={linkUserSchool.user_id} onChange={(event) => setLinkUserSchool({ ...linkUserSchool, user_id: event.target.value })}>
                  <option value="">select user</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.id} - {user.email}
                    </option>
                  ))}
                </select>
                <select value={linkUserSchool.role} onChange={(event) => setLinkUserSchool({ ...linkUserSchool, role: event.target.value })}>
                  <option value="admin">admin</option>
                  <option value="director">director</option>
                  <option value="teacher">teacher</option>
                  <option value="student">student</option>
                  <option value="parent">parent</option>
                </select>
                <button type="submit">Associate</button>
              </form>
              <form className="form" onSubmit={handleDeassociateUserSchool}>
                <h4>Deassociate User from School</h4>
                <select value={linkUserSchool.user_id} onChange={(event) => setLinkUserSchool({ ...linkUserSchool, user_id: event.target.value })}>
                  <option value="">select user</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.id} - {user.email}
                    </option>
                  ))}
                </select>
                <button type="submit">Deassociate</button>
              </form>
              <form className="form" onSubmit={handleLinkUserStudent}>
                <h4>Associate User with Student</h4>
                <select value={linkUserStudent.user_id} onChange={(event) => setLinkUserStudent({ ...linkUserStudent, user_id: event.target.value })}>
                  <option value="">select user</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.id} - {user.email}
                    </option>
                  ))}
                </select>
                <select value={linkUserStudent.student_id} onChange={(event) => setLinkUserStudent({ ...linkUserStudent, student_id: event.target.value })}>
                  <option value="">select student</option>
                  {students.map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.id} - {student.first_name} {student.last_name}
                    </option>
                  ))}
                </select>
                <button type="submit">Associate</button>
              </form>
              <form className="form" onSubmit={handleDeassociateUserStudent}>
                <h4>Deassociate User from Student</h4>
                <select value={linkUserStudent.user_id} onChange={(event) => setLinkUserStudent({ ...linkUserStudent, user_id: event.target.value })}>
                  <option value="">select user</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.id} - {user.email}
                    </option>
                  ))}
                </select>
                <select value={linkUserStudent.student_id} onChange={(event) => setLinkUserStudent({ ...linkUserStudent, student_id: event.target.value })}>
                  <option value="">select student</option>
                  {students.map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.id} - {student.first_name} {student.last_name}
                    </option>
                  ))}
                </select>
                <button type="submit">Deassociate</button>
              </form>
              <form className="form" onSubmit={handleLinkStudentSchool}>
                <h4>Associate Student with School</h4>
                <select value={linkStudentSchool.student_id} onChange={(event) => setLinkStudentSchool({ ...linkStudentSchool, student_id: event.target.value })}>
                  <option value="">select student</option>
                  {students.map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.id} - {student.first_name} {student.last_name}
                    </option>
                  ))}
                </select>
                <button type="submit">Associate</button>
              </form>
              <form className="form" onSubmit={handleDeassociateStudentSchool}>
                <h4>Deassociate Student from School</h4>
                <select value={linkStudentSchool.student_id} onChange={(event) => setLinkStudentSchool({ ...linkStudentSchool, student_id: event.target.value })}>
                  <option value="">select student</option>
                  {students.map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.id} - {student.first_name} {student.last_name}
                    </option>
                  ))}
                </select>
                <button type="submit">Deassociate</button>
              </form>
              <form className="form" onSubmit={handleUpdateUser}>
                <h4>Edit User</h4>
                <select value={updateUser.user_id} onChange={(event) => setUpdateUser({ ...updateUser, user_id: event.target.value })}>
                  <option value="">select user</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.id} - {user.email}
                    </option>
                  ))}
                </select>
                <input placeholder="email" value={updateUser.email} onChange={(event) => setUpdateUser({ ...updateUser, email: event.target.value })} />
                <input placeholder="password" value={updateUser.password} onChange={(event) => setUpdateUser({ ...updateUser, password: event.target.value })} />
                <input placeholder="first name" value={updateUser.first_name} onChange={(event) => setUpdateUser({ ...updateUser, first_name: event.target.value })} />
                <input placeholder="last name" value={updateUser.last_name} onChange={(event) => setUpdateUser({ ...updateUser, last_name: event.target.value })} />
                <select value={updateUser.is_active} onChange={(event) => setUpdateUser({ ...updateUser, is_active: event.target.value })}>
                  <option value="true">active</option>
                  <option value="false">inactive</option>
                </select>
                <button type="submit">Update user</button>
              </form>
              <form className="form" onSubmit={handleUpdateSchool}>
                <h4>Edit School</h4>
                <select value={updateSchool.school_id} onChange={(event) => setUpdateSchool({ ...updateSchool, school_id: event.target.value })}>
                  <option value="">select school</option>
                  {(me?.schools ?? []).map((school) => (
                    <option key={school.school_id} value={school.school_id}>
                      {school.school_name}
                    </option>
                  ))}
                </select>
                <input placeholder="name" value={updateSchool.name} onChange={(event) => setUpdateSchool({ ...updateSchool, name: event.target.value })} />
                <input placeholder="slug" value={updateSchool.slug} onChange={(event) => setUpdateSchool({ ...updateSchool, slug: event.target.value })} />
                <select value={updateSchool.is_active} onChange={(event) => setUpdateSchool({ ...updateSchool, is_active: event.target.value })}>
                  <option value="true">active</option>
                  <option value="false">inactive</option>
                </select>
                <button type="submit">Update school</button>
              </form>
              <form className="form" onSubmit={handleUpdateStudent}>
                <h4>Edit Student</h4>
                <select value={updateStudent.student_id} onChange={(event) => setUpdateStudent({ ...updateStudent, student_id: event.target.value })}>
                  <option value="">select student</option>
                  {students.map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.id} - {student.first_name} {student.last_name}
                    </option>
                  ))}
                </select>
                <input placeholder="first name" value={updateStudent.first_name} onChange={(event) => setUpdateStudent({ ...updateStudent, first_name: event.target.value })} />
                <input placeholder="last name" value={updateStudent.last_name} onChange={(event) => setUpdateStudent({ ...updateStudent, last_name: event.target.value })} />
                <input placeholder="external id" value={updateStudent.external_id} onChange={(event) => setUpdateStudent({ ...updateStudent, external_id: event.target.value })} />
                <button type="submit">Update student</button>
              </form>
              <form className="form" onSubmit={handleDeleteUser}>
                <h4>Delete User</h4>
                <select value={deleteIds.user_id} onChange={(event) => setDeleteIds({ ...deleteIds, user_id: event.target.value })}>
                  <option value="">select user</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.id} - {user.email}
                    </option>
                  ))}
                </select>
                <button type="submit">Delete user</button>
              </form>
              <form className="form" onSubmit={handleDeleteSchool}>
                <h4>Delete School</h4>
                <select value={deleteIds.school_id} onChange={(event) => setDeleteIds({ ...deleteIds, school_id: event.target.value })}>
                  <option value="">select school</option>
                  {(me?.schools ?? []).map((school) => (
                    <option key={school.school_id} value={school.school_id}>
                      {school.school_name}
                    </option>
                  ))}
                </select>
                <button type="submit">Delete school</button>
              </form>
              <form className="form" onSubmit={handleDeleteStudent}>
                <h4>Delete Student</h4>
                <select value={deleteIds.student_id} onChange={(event) => setDeleteIds({ ...deleteIds, student_id: event.target.value })}>
                  <option value="">select student</option>
                  {students.map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.id} - {student.first_name} {student.last_name}
                    </option>
                  ))}
                </select>
                <button type="submit">Delete student</button>
              </form>
              <div>
                <h4>Users in School</h4>
                <ul>
                  {users.map((user) => (
                    <li key={user.id}>{user.id} - {user.email}</li>
                  ))}
                </ul>
                <h4>Students in School</h4>
                <ul>
                  {students.map((student) => (
                    <li key={student.id}>{student.id} - {student.first_name} {student.last_name}</li>
                  ))}
                </ul>
              </div>
            </section>
          )}
          <button onClick={onLogout} type="button">
            Logout
          </button>
        </section>
      )}
    </main>
  );
}

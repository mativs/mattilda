import { useEffect, useMemo, useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:18000";
const TOKEN_KEY = "mattilda_token";
const SCHOOL_KEY = "mattilda_school_id";

const DEFAULT_LIMIT = 10;
const USER_ROLE_OPTIONS = ["admin", "director", "teacher", "student", "parent"];
const FEE_RECURRENCE_OPTIONS = ["monthly", "annual", "one_time"];
const CHARGE_TYPE_OPTIONS = ["fee", "interest", "penalty"];
const CHARGE_STATUS_OPTIONS = ["paid", "unpaid", "cancelled"];

function toDateTimeLocal(value) {
  if (!value) {
    return "";
  }
  const normalized = String(value).replace("Z", "");
  return normalized.slice(0, 16);
}

function currentDateTimeLocal() {
  return toDateTimeLocal(new Date().toISOString());
}

function formatCurrency(value) {
  const numeric = Number(value ?? 0);
  if (Number.isNaN(numeric)) {
    return "$0.00";
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(numeric);
}

function isInvoiceOverdue(invoice) {
  if (!invoice?.due_date) {
    return false;
  }
  const dueDate = new Date(`${invoice.due_date}T23:59:59Z`);
  if (Number.isNaN(dueDate.getTime())) {
    return false;
  }
  return new Date() > dueDate;
}

function usePublicHealth() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);

  useEffect(() => {
    async function loadPing() {
      try {
        const response = await fetch(`${API_URL}/api/v1/ping`);
        if (!response.ok) {
          throw new Error(`Request failed with ${response.status}`);
        }
        setPayload(await response.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadPing();
  }, []);

  return { loading, error, payload };
}

function LoginPage({ username, setUsername, password, setPassword, loading, onSubmit, error, health }) {
  return (
    <main className="login-page">
      <section className="login-card">
        <h1>Mattilda</h1>
        <p>Administrative portal</p>
        {health.loading && <p className="muted">Checking backend status...</p>}
        {health.payload && (
          <p className="muted">
            API {health.payload.db_connected ? "DB OK" : "DB OFF"} | Redis {health.payload.redis_connected ? "OK" : "OFF"}
          </p>
        )}
        {(error || health.error) && <p className="error">{error || health.error}</p>}
        <form className="form" onSubmit={onSubmit}>
          <label>
            Email
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <button disabled={loading} type="submit">
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}

function SectionTitle({ children }) {
  return <h2 className="section-title">{children}</h2>;
}

function Modal({ title, children, onClose, onSubmit, submitLabel, danger = false }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="ghost" onClick={onClose} type="button">
            Close
          </button>
        </div>
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          {children}
          <div className="modal-actions">
            <button className="ghost" onClick={onClose} type="button">
              Cancel
            </button>
            <button className={danger ? "danger" : ""} type="submit">
              {submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DashboardPage({ activeSchool, isSchoolAdmin, schoolFinancialSummary }) {
  return (
    <section className="page-card">
      <SectionTitle>Dashboard</SectionTitle>
      {activeSchool && (
        <>
          <p>
            Active school: <strong>{activeSchool.name}</strong>
          </p>
          {isSchoolAdmin ? (
            <div className="kv-grid">
              <div>
                <span className="muted">Billed (open invoices)</span>
                <p>{formatCurrency(schoolFinancialSummary?.total_billed_amount)}</p>
              </div>
              <div>
                <span className="muted">Total charged</span>
                <p>{formatCurrency(schoolFinancialSummary?.total_charged_amount)}</p>
              </div>
              <div>
                <span className="muted">Total paid</span>
                <p>{formatCurrency(schoolFinancialSummary?.total_paid_amount)}</p>
              </div>
              <div>
                <span className="muted">Pending to pay (net unpaid)</span>
                <p>{formatCurrency(schoolFinancialSummary?.total_pending_amount)}</p>
              </div>
              <div>
                <span className="muted">Students</span>
                <p>{schoolFinancialSummary?.student_count ?? 0}</p>
              </div>
            </div>
          ) : (
            <p className="muted">No financial metrics available for your role.</p>
          )}
        </>
      )}
    </section>
  );
}

function ProfilePage({ me, selectedSchool }) {
  if (!me) {
    return null;
  }
  return (
    <section className="page-card">
      <SectionTitle>My Profile</SectionTitle>
      <div className="kv-grid">
        <div>
          <span className="muted">Email</span>
          <p>{me.email}</p>
        </div>
        <div>
          <span className="muted">Name</span>
          <p>
            {me.profile.first_name} {me.profile.last_name}
          </p>
        </div>
        {selectedSchool && (
          <div>
            <span className="muted">Roles in current school</span>
            <p>{selectedSchool.roles.join(", ")}</p>
          </div>
        )}
      </div>
    </section>
  );
}

function StudentDetailPage({ selectedSchoolId, request, isSchoolAdmin }) {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const [student, setStudent] = useState(null);
  const [summary, setSummary] = useState(null);
  const [unpaidRows, setUnpaidRows] = useState([]);
  const [unpaidPagination, setUnpaidPagination] = useState(null);
  const [unpaidSearch, setUnpaidSearch] = useState("");
  const [unpaidOffset, setUnpaidOffset] = useState(0);
  const [invoiceRows, setInvoiceRows] = useState([]);
  const [invoicePagination, setInvoicePagination] = useState(null);
  const [invoiceSearch, setInvoiceSearch] = useState("");
  const [invoiceOffset, setInvoiceOffset] = useState(0);
  const [paymentRows, setPaymentRows] = useState([]);
  const [paymentPagination, setPaymentPagination] = useState(null);
  const [paymentSearch, setPaymentSearch] = useState("");
  const [paymentOffset, setPaymentOffset] = useState(0);
  const [createChargeModalOpen, setCreateChargeModalOpen] = useState(false);
  const [createChargeForm, setCreateChargeForm] = useState({
    description: "",
    amount: "",
    period: "",
    debt_created_at: currentDateTimeLocal(),
    due_date: "",
    charge_type: "fee",
  });
  const [payModalOpen, setPayModalOpen] = useState(false);
  const [payForm, setPayForm] = useState({ amount: "", method: "transfer", paid_at: currentDateTimeLocal() });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const openInvoice = useMemo(() => {
    const openRows = invoiceRows.filter((row) => row.status === "open");
    if (openRows.length === 0) {
      return null;
    }
    return [...openRows].sort((a, b) => b.id - a.id)[0];
  }, [invoiceRows]);

  const payButtonDisabledReason = useMemo(() => {
    if (!openInvoice) {
      return "There is no open invoice";
    }
    if (isInvoiceOverdue(openInvoice)) {
      return "Invoice is due. Generate a new one";
    }
    return "";
  }, [openInvoice]);

  async function loadUnpaid(nextOffset = unpaidOffset, nextSearch = unpaidSearch) {
    const query = new URLSearchParams({ offset: String(nextOffset), limit: String(DEFAULT_LIMIT) });
    if (nextSearch.trim()) {
      query.set("search", nextSearch.trim());
    }
    const payload = await request(`/api/v1/students/${studentId}/charges/unpaid?${query.toString()}`);
    setUnpaidRows(payload.items ?? []);
    setUnpaidPagination(payload.pagination ?? null);
    return payload;
  }

  async function loadInvoices(nextOffset = invoiceOffset, nextSearch = invoiceSearch) {
    const query = new URLSearchParams({ offset: String(nextOffset), limit: String(DEFAULT_LIMIT) });
    if (nextSearch.trim()) {
      query.set("search", nextSearch.trim());
    }
    const payload = await request(`/api/v1/students/${studentId}/invoices?${query.toString()}`);
    setInvoiceRows(payload.items ?? []);
    setInvoicePagination(payload.pagination ?? null);
  }

  async function loadPayments(nextOffset = paymentOffset, nextSearch = paymentSearch) {
    const query = new URLSearchParams({ offset: String(nextOffset), limit: String(DEFAULT_LIMIT) });
    if (nextSearch.trim()) {
      query.set("search", nextSearch.trim());
    }
    const payload = await request(`/api/v1/students/${studentId}/payments?${query.toString()}`);
    setPaymentRows(payload.items ?? []);
    setPaymentPagination(payload.pagination ?? null);
  }

  async function refreshStudentDashboardData() {
    const summaryPayload = await request(`/api/v1/students/${studentId}/financial-summary`);
    setSummary(summaryPayload);
    await Promise.all([
      loadUnpaid(unpaidOffset, unpaidSearch),
      loadInvoices(invoiceOffset, invoiceSearch),
      loadPayments(paymentOffset, paymentSearch),
    ]);
  }

  useEffect(() => {
    async function loadStudentDashboard() {
      if (!selectedSchoolId || !studentId) {
        return;
      }
      setLoading(true);
      setError("");
      try {
        setUnpaidOffset(0);
        setInvoiceOffset(0);
        setPaymentOffset(0);
        setUnpaidSearch("");
        setInvoiceSearch("");
        setPaymentSearch("");
        const [studentPayload, summaryPayload] = await Promise.all([
          request(`/api/v1/students/${studentId}`),
          request(`/api/v1/students/${studentId}/financial-summary`),
        ]);
        setStudent(studentPayload);
        setSummary(summaryPayload);
        await Promise.all([loadUnpaid(0, ""), loadInvoices(0, ""), loadPayments(0, "")]);
      } catch (err) {
        setError(err.message);
        setStudent(null);
        setSummary(null);
        setUnpaidRows([]);
        setInvoiceRows([]);
        setPaymentRows([]);
      } finally {
        setLoading(false);
      }
    }
    loadStudentDashboard();
  }, [selectedSchoolId, studentId]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    loadUnpaid(unpaidOffset, unpaidSearch).catch((err) => setError(err.message));
  }, [unpaidOffset]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    const timer = setTimeout(() => {
      setUnpaidOffset(0);
      loadUnpaid(0, unpaidSearch).catch((err) => setError(err.message));
    }, 250);
    return () => clearTimeout(timer);
  }, [unpaidSearch]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    loadInvoices(invoiceOffset, invoiceSearch).catch((err) => setError(err.message));
  }, [invoiceOffset]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    const timer = setTimeout(() => {
      setInvoiceOffset(0);
      loadInvoices(0, invoiceSearch).catch((err) => setError(err.message));
    }, 250);
    return () => clearTimeout(timer);
  }, [invoiceSearch]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    loadPayments(paymentOffset, paymentSearch).catch((err) => setError(err.message));
  }, [paymentOffset]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    const timer = setTimeout(() => {
      setPaymentOffset(0);
      loadPayments(0, paymentSearch).catch((err) => setError(err.message));
    }, 250);
    return () => clearTimeout(timer);
  }, [paymentSearch]);

  return (
    <section className="page-card">
      <SectionTitle>Student Financial Dashboard</SectionTitle>
      {loading && <p className="muted">Loading student...</p>}
      {error && <p className="error">{error}</p>}
      {student && (
        <>
          <div className="row-actions">
            <p>
              {student.first_name} {student.last_name}
            </p>
            <button
              className="ghost"
              disabled={!openInvoice}
              onClick={() => {
                if (!openInvoice) {
                  return;
                }
                navigate(`/students/${studentId}/billing/${openInvoice.id}`);
              }}
              type="button"
            >
              View Open Invoice
            </button>
            <button
              className="ghost"
              disabled={Boolean(payButtonDisabledReason)}
              onClick={() => {
                if (!openInvoice) {
                  return;
                }
                setPayForm({
                  amount: openInvoice.total_amount ? String(openInvoice.total_amount) : "",
                  method: "transfer",
                  paid_at: currentDateTimeLocal(),
                });
                setPayModalOpen(true);
              }}
              type="button"
            >
              Pay
            </button>
          </div>
          {!openInvoice && <p className="muted">There is no open invoice</p>}
          {openInvoice && payButtonDisabledReason && <p className="muted">{payButtonDisabledReason}</p>}
          <div className="kv-grid">
            <div>
              <span className="muted">Account status</span>
              <p>{summary?.account_status ?? "-"}</p>
            </div>
            <div>
              <span className="muted">Net unpaid</span>
              <p>{formatCurrency(summary?.total_unpaid_amount)}</p>
            </div>
            <div>
              <span className="muted">Total charged</span>
              <p>{formatCurrency(summary?.total_charged_amount)}</p>
            </div>
            <div>
              <span className="muted">Total paid</span>
              <p>{formatCurrency(summary?.total_paid_amount)}</p>
            </div>
            <div>
              <span className="muted">Unpaid debt</span>
              <p>{formatCurrency(summary?.total_unpaid_debt_amount)}</p>
            </div>
            <div>
              <span className="muted">Available credit</span>
              <p>{formatCurrency(summary?.total_unpaid_credit_amount)}</p>
            </div>
          </div>

          <div className="association-box">
            <p className="muted">Unpaid charges</p>
            <div className="toolbar">
              <input
                placeholder="Search unpaid charges..."
                value={unpaidSearch}
                onChange={(event) => setUnpaidSearch(event.target.value)}
              />
              {isSchoolAdmin && (
                <button
                  className="ghost"
                  onClick={() => {
                    setCreateChargeForm({
                      description: "",
                      amount: "",
                      period: "",
                      debt_created_at: currentDateTimeLocal(),
                      due_date: "",
                      charge_type: "fee",
                    });
                    setCreateChargeModalOpen(true);
                  }}
                  type="button"
                >
                  Add Charge
                </button>
              )}
            </div>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Description</th>
                  <th>Amount</th>
                  <th>Due date</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {unpaidRows.map((charge) => (
                  <tr key={charge.id}>
                    <td>{charge.id}</td>
                    <td>{charge.description}</td>
                    <td>{formatCurrency(charge.amount)}</td>
                    <td>{charge.due_date}</td>
                    <td>{charge.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <PaginationControls pagination={unpaidPagination} onChange={setUnpaidOffset} />
          </div>

          <div className="association-box">
            <p className="muted">Invoices</p>
            <div className="toolbar">
              <input
                placeholder="Search invoices..."
                value={invoiceSearch}
                onChange={(event) => setInvoiceSearch(event.target.value)}
              />
              {isSchoolAdmin && (
                <button
                  className="ghost"
                  onClick={async () => {
                    try {
                      setError("");
                      await request(`/api/v1/students/${studentId}/invoices/generate`, { method: "POST" });
                      await refreshStudentDashboardData();
                    } catch (err) {
                      setError(err.message);
                    }
                  }}
                  type="button"
                >
                  Generate Invoice
                </button>
              )}
            </div>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Period</th>
                  <th>Issued</th>
                  <th>Due</th>
                  <th>Total</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {invoiceRows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.period}</td>
                    <td>{row.issued_at}</td>
                    <td>{row.due_date}</td>
                    <td>{formatCurrency(row.total_amount)}</td>
                    <td>{row.status}</td>
                    <td className="row-actions">
                      <NavLink className="ghost action-link" to={`/students/${studentId}/billing/${row.id}`}>
                        Open
                      </NavLink>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <PaginationControls pagination={invoicePagination} onChange={setInvoiceOffset} />
          </div>

          <div className="association-box">
            <p className="muted">Payments</p>
            <div className="toolbar">
              <input
                placeholder="Search payments..."
                value={paymentSearch}
                onChange={(event) => setPaymentSearch(event.target.value)}
              />
            </div>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Amount</th>
                  <th>Paid at</th>
                  <th>Method</th>
                  <th>Invoice</th>
                </tr>
              </thead>
              <tbody>
                {paymentRows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{formatCurrency(row.amount)}</td>
                    <td>{row.paid_at}</td>
                    <td>{row.method}</td>
                    <td>{row.invoice ? `#${row.invoice.id}` : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <PaginationControls pagination={paymentPagination} onChange={setPaymentOffset} />
          </div>
        </>
      )}
      {payModalOpen && openInvoice && (
        <Modal
          title={`Pay invoice #${openInvoice.id}`}
          onClose={() => setPayModalOpen(false)}
          onSubmit={async () => {
            try {
              setError("");
              const paidAtIso = payForm.paid_at ? new Date(payForm.paid_at).toISOString() : new Date().toISOString();
              await request("/api/v1/payments", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  student_id: Number(studentId),
                  invoice_id: openInvoice.id,
                  amount: payForm.amount,
                  paid_at: paidAtIso,
                  method: payForm.method,
                }),
              });
              setPayModalOpen(false);
              await refreshStudentDashboardData();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Pay"
        >
          <p className="muted">Invoice total: {formatCurrency(openInvoice.total_amount)}</p>
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            value={payForm.amount}
            onChange={(event) => setPayForm({ ...payForm, amount: event.target.value })}
          />
          <select value={payForm.method} onChange={(event) => setPayForm({ ...payForm, method: event.target.value })}>
            <option value="transfer">transfer</option>
            <option value="cash">cash</option>
            <option value="card">card</option>
          </select>
          <input
            type="datetime-local"
            value={payForm.paid_at}
            onChange={(event) => setPayForm({ ...payForm, paid_at: event.target.value })}
          />
        </Modal>
      )}
      {createChargeModalOpen && (
        <Modal
          title={`Add charge for ${student?.first_name ?? ""} ${student?.last_name ?? ""}`.trim()}
          onClose={() => setCreateChargeModalOpen(false)}
          onSubmit={async () => {
            try {
              setError("");
              await request("/api/v1/charges", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  student_id: Number(studentId),
                  fee_definition_id: null,
                  description: createChargeForm.description,
                  amount: createChargeForm.amount,
                  period: createChargeForm.period || null,
                  debt_created_at: createChargeForm.debt_created_at
                    ? new Date(createChargeForm.debt_created_at).toISOString()
                    : new Date().toISOString(),
                  due_date: createChargeForm.due_date,
                  charge_type: createChargeForm.charge_type,
                  status: "unpaid",
                }),
              });
              setCreateChargeModalOpen(false);
              await refreshStudentDashboardData();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Create charge"
        >
          <input
            placeholder="Description"
            value={createChargeForm.description}
            onChange={(event) => setCreateChargeForm({ ...createChargeForm, description: event.target.value })}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            value={createChargeForm.amount}
            onChange={(event) => setCreateChargeForm({ ...createChargeForm, amount: event.target.value })}
          />
          <input
            placeholder="Period (YYYY-MM)"
            value={createChargeForm.period}
            onChange={(event) => setCreateChargeForm({ ...createChargeForm, period: event.target.value })}
          />
          <input
            type="datetime-local"
            value={createChargeForm.debt_created_at}
            onChange={(event) => setCreateChargeForm({ ...createChargeForm, debt_created_at: event.target.value })}
          />
          <input
            type="date"
            value={createChargeForm.due_date}
            onChange={(event) => setCreateChargeForm({ ...createChargeForm, due_date: event.target.value })}
          />
          <select
            value={createChargeForm.charge_type}
            onChange={(event) => setCreateChargeForm({ ...createChargeForm, charge_type: event.target.value })}
          >
            {CHARGE_TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </Modal>
      )}
    </section>
  );
}

function StudentBillingPage({ selectedSchoolId, request, isSchoolAdmin }) {
  const { studentId } = useParams();
  const [student, setStudent] = useState(null);
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");

  async function loadInvoices(nextOffset = offset, nextSearch = search) {
    const query = new URLSearchParams({ offset: String(nextOffset), limit: String(DEFAULT_LIMIT) });
    if (nextSearch) {
      query.set("search", nextSearch);
    }
    const [studentPayload, listPayload] = await Promise.all([
      request(`/api/v1/students/${studentId}`),
      request(`/api/v1/students/${studentId}/invoices?${query.toString()}`),
    ]);
    setStudent(studentPayload);
    setRows(listPayload.items ?? []);
    setPagination(listPayload.pagination ?? null);
  }

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    setError("");
    loadInvoices(0, "").catch((err) => setError(err.message));
    setOffset(0);
    setSearch("");
  }, [selectedSchoolId, studentId]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    loadInvoices(offset, search).catch((err) => setError(err.message));
  }, [offset]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    const timer = setTimeout(() => {
      setOffset(0);
      loadInvoices(0, search).catch((err) => setError(err.message));
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);

  return (
    <section className="page-card">
      <SectionTitle>Student Billing</SectionTitle>
      {student && (
        <p>
          {student.first_name} {student.last_name}
        </p>
      )}
      {error && <p className="error">{error}</p>}
      <div className="toolbar">
        <input placeholder="Search by period or status..." value={search} onChange={(event) => setSearch(event.target.value)} />
        {isSchoolAdmin && (
          <button
            className="ghost"
            onClick={async () => {
              try {
                setError("");
                await request(`/api/v1/students/${studentId}/invoices/generate`, { method: "POST" });
                await loadInvoices(0, search);
                setOffset(0);
              } catch (err) {
                setError(err.message);
              }
            }}
            type="button"
          >
            Generate Invoice
          </button>
        )}
      </div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Period</th>
            <th>Issued</th>
            <th>Due</th>
            <th>Total</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{row.period}</td>
              <td>{row.issued_at}</td>
              <td>{row.due_date}</td>
              <td>{formatCurrency(row.total_amount)}</td>
              <td>{row.status}</td>
              <td className="row-actions">
                <NavLink className="ghost action-link" to={`/students/${studentId}/billing/${row.id}`}>
                  Open
                </NavLink>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <PaginationControls pagination={pagination} onChange={setOffset} />
    </section>
  );
}

function InvoiceDetailPage({ selectedSchoolId, request }) {
  const { invoiceId } = useParams();
  const [invoice, setInvoice] = useState(null);
  const [payModalOpen, setPayModalOpen] = useState(false);
  const [payForm, setPayForm] = useState({ amount: "", method: "transfer", paid_at: currentDateTimeLocal() });
  const [error, setError] = useState("");

  const payDisabledReason = useMemo(() => {
    if (!invoice) {
      return "There is no open invoice";
    }
    if (invoice.status !== "open") {
      return "There is no open invoice";
    }
    if (isInvoiceOverdue(invoice)) {
      return "Invoice is due. Generate a new one";
    }
    return "";
  }, [invoice]);

  useEffect(() => {
    async function loadInvoice() {
      if (!selectedSchoolId || !invoiceId) {
        return;
      }
      setError("");
      try {
        const payload = await request(`/api/v1/invoices/${invoiceId}`);
        setInvoice(payload);
      } catch (err) {
        setError(err.message);
        setInvoice(null);
      }
    }
    loadInvoice();
  }, [selectedSchoolId, invoiceId, request]);

  return (
    <section className="page-card">
      <SectionTitle>Invoice Detail</SectionTitle>
      {error && <p className="error">{error}</p>}
      {invoice && (
        <>
          <div className="kv-grid">
            <div>
              <span className="muted">Invoice</span>
              <p>#{invoice.id}</p>
            </div>
            <div>
              <span className="muted">Period</span>
              <p>{invoice.period}</p>
            </div>
            <div>
              <span className="muted">Issued</span>
              <p>{invoice.issued_at}</p>
            </div>
            <div>
              <span className="muted">Due</span>
              <p>{invoice.due_date}</p>
            </div>
            <div>
              <span className="muted">Total</span>
              <p>{formatCurrency(invoice.total_amount)}</p>
            </div>
            <div>
              <span className="muted">Status</span>
              <p>{invoice.status}</p>
            </div>
          </div>
          <div className="row-actions">
            <button className="ghost" onClick={() => window.print()} type="button">
              Print
            </button>
            <button
              className="ghost"
              disabled={Boolean(payDisabledReason)}
              onClick={() => {
                if (!invoice) {
                  return;
                }
                setPayForm({
                  amount: invoice.total_amount ? String(invoice.total_amount) : "",
                  method: "transfer",
                  paid_at: currentDateTimeLocal(),
                });
                setPayModalOpen(true);
              }}
              type="button"
            >
              Pay
            </button>
          </div>
          {payDisabledReason && <p className="muted">{payDisabledReason}</p>}
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Description</th>
                <th>Type</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {invoice.items.map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.description}</td>
                  <td>{item.charge_type}</td>
                  <td>{formatCurrency(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {payModalOpen && invoice && (
        <Modal
          title={`Pay invoice #${invoice.id}`}
          onClose={() => setPayModalOpen(false)}
          onSubmit={async () => {
            try {
              setError("");
              const paidAtIso = payForm.paid_at ? new Date(payForm.paid_at).toISOString() : new Date().toISOString();
              await request("/api/v1/payments", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  student_id: invoice.student_id,
                  invoice_id: invoice.id,
                  amount: payForm.amount,
                  paid_at: paidAtIso,
                  method: payForm.method,
                }),
              });
              setPayModalOpen(false);
              const payload = await request(`/api/v1/invoices/${invoiceId}`);
              setInvoice(payload);
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Pay"
        >
          <p className="muted">Invoice total: {formatCurrency(invoice.total_amount)}</p>
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            value={payForm.amount}
            onChange={(event) => setPayForm({ ...payForm, amount: event.target.value })}
          />
          <select value={payForm.method} onChange={(event) => setPayForm({ ...payForm, method: event.target.value })}>
            <option value="transfer">transfer</option>
            <option value="cash">cash</option>
            <option value="card">card</option>
          </select>
          <input
            type="datetime-local"
            value={payForm.paid_at}
            onChange={(event) => setPayForm({ ...payForm, paid_at: event.target.value })}
          />
        </Modal>
      )}
    </section>
  );
}

function StudentPaymentsPage({ selectedSchoolId, request }) {
  const { studentId } = useParams();
  const [student, setStudent] = useState(null);
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");

  async function loadPayments(nextOffset = offset, nextSearch = search) {
    const query = new URLSearchParams({ offset: String(nextOffset), limit: String(DEFAULT_LIMIT) });
    if (nextSearch) {
      query.set("search", nextSearch);
    }
    const [studentPayload, listPayload] = await Promise.all([
      request(`/api/v1/students/${studentId}`),
      request(`/api/v1/students/${studentId}/payments?${query.toString()}`),
    ]);
    setStudent(studentPayload);
    setRows(listPayload.items ?? []);
    setPagination(listPayload.pagination ?? null);
  }

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    setError("");
    loadPayments(0, "").catch((err) => setError(err.message));
    setOffset(0);
    setSearch("");
  }, [selectedSchoolId, studentId]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    loadPayments(offset, search).catch((err) => setError(err.message));
  }, [offset]);

  useEffect(() => {
    if (!selectedSchoolId || !studentId) {
      return;
    }
    const timer = setTimeout(() => {
      setOffset(0);
      loadPayments(0, search).catch((err) => setError(err.message));
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);

  return (
    <section className="page-card">
      <SectionTitle>Student Payments</SectionTitle>
      {student && (
        <p>
          {student.first_name} {student.last_name}
        </p>
      )}
      {error && <p className="error">{error}</p>}
      <div className="toolbar">
        <input placeholder="Search by method or amount..." value={search} onChange={(event) => setSearch(event.target.value)} />
      </div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Amount</th>
            <th>Paid at</th>
            <th>Method</th>
            <th>Invoice</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{formatCurrency(row.amount)}</td>
              <td>{row.paid_at}</td>
              <td>{row.method}</td>
              <td>{row.invoice ? `#${row.invoice.id}` : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <PaginationControls pagination={pagination} onChange={setOffset} />
    </section>
  );
}

function TableToolbar({ search, onSearch, onCreate }) {
  return (
    <div className="toolbar">
      <input placeholder="Search..." value={search} onChange={(event) => onSearch(event.target.value)} />
      <button onClick={onCreate} type="button">
        Create
      </button>
    </div>
  );
}

function PaginationControls({ pagination, onChange }) {
  if (!pagination) {
    return null;
  }
  const { offset, limit, filtered_total: filteredTotal, has_next: hasNext, has_prev: hasPrev } = pagination;
  const start = filteredTotal === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, filteredTotal);
  return (
    <div className="pagination">
      <span className="muted">
        Showing {start}-{end} of {filteredTotal}
      </span>
      <div className="pagination-actions">
        <button disabled={!hasPrev} onClick={() => onChange(Math.max(0, offset - limit))} type="button">
          Prev
        </button>
        <button disabled={!hasNext} onClick={() => onChange(offset + limit)} type="button">
          Next
        </button>
      </div>
    </div>
  );
}

function UsersConfigPage({ request, selectedSchoolId }) {
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [schoolOptions, setSchoolOptions] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [deleteUser, setDeleteUser] = useState(null);
  const [createForm, setCreateForm] = useState({ email: "", password: "", first_name: "", last_name: "", is_active: "true" });
  const [editForm, setEditForm] = useState({ email: "", password: "", first_name: "", last_name: "", is_active: "true" });
  const [createMembershipRows, setCreateMembershipRows] = useState([]);
  const [createSchoolToAdd, setCreateSchoolToAdd] = useState("");
  const [createRoleToAdd, setCreateRoleToAdd] = useState("teacher");
  const [editMembershipRows, setEditMembershipRows] = useState([]);
  const [editInitialMembershipRows, setEditInitialMembershipRows] = useState([]);
  const [editSchoolToAdd, setEditSchoolToAdd] = useState("");
  const [editRoleToAdd, setEditRoleToAdd] = useState("teacher");

  async function loadUsers() {
    if (!selectedSchoolId) {
      return;
    }
    try {
      const query = new URLSearchParams({ offset: String(offset), limit: String(DEFAULT_LIMIT) });
      if (search.trim()) {
        query.set("search", search.trim());
      }
      const payload = await request(`/api/v1/users?${query.toString()}`);
      setRows(payload.items ?? []);
      setPagination(payload.pagination ?? null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadSchoolsOptions() {
    if (!selectedSchoolId) {
      return;
    }
    try {
      const payload = await request("/api/v1/schools?offset=0&limit=100");
      setSchoolOptions(payload.items ?? []);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    setOffset(0);
  }, [search, selectedSchoolId]);

  useEffect(() => {
    loadSchoolsOptions();
  }, [selectedSchoolId]);

  useEffect(() => {
    loadUsers();
  }, [offset, selectedSchoolId, search]);

  function sortMembershipRows(values) {
    return [...values].sort((a, b) => {
      const schoolA = (a.school_name ?? "").toLowerCase();
      const schoolB = (b.school_name ?? "").toLowerCase();
      if (schoolA !== schoolB) {
        return schoolA.localeCompare(schoolB);
      }
      return a.role.localeCompare(b.role);
    });
  }

  function membershipKey(value) {
    return `${value.school_id}:${value.role}`;
  }

  function schoolNameById(schoolId) {
    const school = schoolOptions.find((item) => item.id === schoolId);
    return school ? school.name : `School #${schoolId}`;
  }

  function addMembershipRow(rowsValue, schoolId, role, schoolName) {
    const row = { school_id: schoolId, school_name: schoolName, role };
    if (rowsValue.some((item) => membershipKey(item) === membershipKey(row))) {
      return rowsValue;
    }
    return sortMembershipRows([...rowsValue, row]);
  }

  function removeMembershipRow(rowsValue, rowToRemove) {
    return rowsValue.filter((item) => membershipKey(item) !== membershipKey(rowToRemove));
  }

  function openEdit(user) {
    setEditUser(user);
    setEditForm({
      email: user.email ?? "",
      password: "",
      first_name: user.profile?.first_name ?? "",
      last_name: user.profile?.last_name ?? "",
      is_active: String(user.is_active),
    });
    const flattenedRows = sortMembershipRows(
      (user.schools ?? []).flatMap((school) =>
        (school.roles ?? []).map((role) => ({
          school_id: school.school_id,
          school_name: school.school_name,
          role,
        })),
      ),
    );
    setEditMembershipRows(flattenedRows);
    setEditInitialMembershipRows(flattenedRows);
    setEditSchoolToAdd("");
    setEditRoleToAdd("teacher");
  }

  return (
    <section className="page-card">
      <SectionTitle>Users</SectionTitle>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      <TableToolbar
        search={search}
        onSearch={setSearch}
        onCreate={() => {
          setError("");
          setCreateOpen(true);
          setCreateMembershipRows([]);
          setCreateSchoolToAdd("");
          setCreateRoleToAdd("teacher");
        }}
      />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Email</th>
            <th>Name</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{row.email}</td>
              <td>
                {row.profile?.first_name} {row.profile?.last_name}
              </td>
              <td>{row.is_active ? "yes" : "no"}</td>
              <td className="row-actions">
                <button className="ghost" onClick={() => openEdit(row)} type="button">
                  Edit
                </button>
                <button className="danger" onClick={() => setDeleteUser(row)} type="button">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <PaginationControls pagination={pagination} onChange={setOffset} />

      {createOpen && (
        <Modal
          title="Create user"
          onClose={() => setCreateOpen(false)}
          onSubmit={async () => {
            try {
              const createdUser = await request("/api/v1/users", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  email: createForm.email,
                  password: createForm.password,
                  is_active: createForm.is_active === "true",
                  profile: { first_name: createForm.first_name, last_name: createForm.last_name },
                }),
              });
              const newUserId = createdUser?.id;
              if (newUserId) {
                for (const row of createMembershipRows) {
                  await request(`/api/v1/schools/${row.school_id}/users`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: newUserId, role: row.role }),
                  });
                }
              }
              setCreateOpen(false);
              setCreateForm({ email: "", password: "", first_name: "", last_name: "", is_active: "true" });
              setCreateMembershipRows([]);
              setCreateSchoolToAdd("");
              setCreateRoleToAdd("teacher");
              setMessage("User created");
              await loadUsers();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Create"
        >
          <input placeholder="Email" value={createForm.email} onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })} />
          <input
            type="password"
            placeholder="Password"
            value={createForm.password}
            onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
          />
          <input
            placeholder="First name"
            value={createForm.first_name}
            onChange={(e) => setCreateForm({ ...createForm, first_name: e.target.value })}
          />
          <input
            placeholder="Last name"
            value={createForm.last_name}
            onChange={(e) => setCreateForm({ ...createForm, last_name: e.target.value })}
          />
          <select value={createForm.is_active} onChange={(e) => setCreateForm({ ...createForm, is_active: e.target.value })}>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
          <div className="association-box">
            <p className="muted">School roles</p>
            <div className="association-row triple">
              <select value={createSchoolToAdd} onChange={(e) => setCreateSchoolToAdd(e.target.value)}>
                <option value="">Select school</option>
                {schoolOptions.map((school) => (
                  <option key={school.id} value={school.id}>
                    {school.name}
                  </option>
                ))}
              </select>
              <select value={createRoleToAdd} onChange={(e) => setCreateRoleToAdd(e.target.value)}>
                {USER_ROLE_OPTIONS.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
              <button
                className="ghost"
                onClick={() => {
                  const schoolId = Number(createSchoolToAdd);
                  if (!schoolId) {
                    return;
                  }
                  setCreateMembershipRows(
                    addMembershipRow(createMembershipRows, schoolId, createRoleToAdd, schoolNameById(schoolId)),
                  );
                }}
                type="button"
              >
                Add
              </button>
            </div>
            <table className="modal-association-table">
              <thead>
                <tr>
                  <th>School</th>
                  <th>Role</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {createMembershipRows.map((row) => (
                  <tr key={membershipKey(row)}>
                    <td>{row.school_name}</td>
                    <td>{row.role}</td>
                    <td className="row-actions">
                      <button
                        className="danger"
                        onClick={() => setCreateMembershipRows(removeMembershipRow(createMembershipRows, row))}
                        type="button"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Modal>
      )}

      {editUser && (
        <Modal
          title={`Edit user #${editUser.id}`}
          onClose={() => setEditUser(null)}
          onSubmit={async () => {
            try {
              const initialKeys = new Set(editInitialMembershipRows.map(membershipKey));
              const currentKeys = new Set(editMembershipRows.map(membershipKey));
              const rowsToAdd = editMembershipRows.filter((row) => !initialKeys.has(membershipKey(row)));
              const rowsToRemove = editInitialMembershipRows.filter((row) => !currentKeys.has(membershipKey(row)));
              await request(`/api/v1/users/${editUser.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  email: editForm.email || undefined,
                  password: editForm.password || undefined,
                  is_active: editForm.is_active === "true",
                  profile: { first_name: editForm.first_name || undefined, last_name: editForm.last_name || undefined },
                  associations: {
                    add: {
                      school_roles: rowsToAdd.map((row) => ({ school_id: row.school_id, role: row.role })),
                    },
                    remove: {
                      school_roles: rowsToRemove.map((row) => ({ school_id: row.school_id, role: row.role })),
                    },
                  },
                }),
              });
              setEditUser(null);
              setEditMembershipRows([]);
              setEditInitialMembershipRows([]);
              setEditSchoolToAdd("");
              setEditRoleToAdd("teacher");
              setMessage("User updated");
              await loadUsers();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Update"
        >
          <input placeholder="Email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
          <input
            type="password"
            placeholder="Password (optional)"
            value={editForm.password}
            onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
          />
          <input
            placeholder="First name"
            value={editForm.first_name}
            onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
          />
          <input
            placeholder="Last name"
            value={editForm.last_name}
            onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
          />
          <select value={editForm.is_active} onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value })}>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
          <div className="association-box">
            <p className="muted">School roles</p>
            <div className="association-row triple">
              <select value={editSchoolToAdd} onChange={(e) => setEditSchoolToAdd(e.target.value)}>
                <option value="">Select school</option>
                {schoolOptions.map((school) => (
                  <option key={school.id} value={school.id}>
                    {school.name}
                  </option>
                ))}
              </select>
              <select value={editRoleToAdd} onChange={(e) => setEditRoleToAdd(e.target.value)}>
                {USER_ROLE_OPTIONS.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
              <button
                className="ghost"
                onClick={() => {
                  const schoolId = Number(editSchoolToAdd);
                  if (!schoolId) {
                    return;
                  }
                  setEditMembershipRows(addMembershipRow(editMembershipRows, schoolId, editRoleToAdd, schoolNameById(schoolId)));
                }}
                type="button"
              >
                Add
              </button>
            </div>
            <table className="modal-association-table">
              <thead>
                <tr>
                  <th>School</th>
                  <th>Role</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {editMembershipRows.map((row) => (
                  <tr key={membershipKey(row)}>
                    <td>{row.school_name}</td>
                    <td>{row.role}</td>
                    <td className="row-actions">
                      <button
                        className="danger"
                        onClick={() => setEditMembershipRows(removeMembershipRow(editMembershipRows, row))}
                        type="button"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Modal>
      )}

      {deleteUser && (
        <Modal
          danger
          title={`Delete user #${deleteUser.id}?`}
          onClose={() => setDeleteUser(null)}
          onSubmit={async () => {
            try {
              await request(`/api/v1/users/${deleteUser.id}`, { method: "DELETE" });
              setDeleteUser(null);
              setMessage("User deleted");
              await loadUsers();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Delete"
        >
          <p>This action cannot be undone.</p>
        </Modal>
      )}
    </section>
  );
}

function StudentsConfigPage({ request, selectedSchoolId }) {
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editStudent, setEditStudent] = useState(null);
  const [deleteStudent, setDeleteStudent] = useState(null);
  const [createForm, setCreateForm] = useState({ first_name: "", last_name: "", external_id: "" });
  const [editForm, setEditForm] = useState({ first_name: "", last_name: "", external_id: "" });
  const [userOptions, setUserOptions] = useState([]);
  const [schoolOptions, setSchoolOptions] = useState([]);
  const [createSelectedUserIds, setCreateSelectedUserIds] = useState([]);
  const [createSelectedSchoolIds, setCreateSelectedSchoolIds] = useState([]);
  const [createUserToAdd, setCreateUserToAdd] = useState("");
  const [createSchoolToAdd, setCreateSchoolToAdd] = useState("");
  const [editSelectedUserIds, setEditSelectedUserIds] = useState([]);
  const [editSelectedSchoolIds, setEditSelectedSchoolIds] = useState([]);
  const [editInitialUserIds, setEditInitialUserIds] = useState([]);
  const [editInitialSchoolIds, setEditInitialSchoolIds] = useState([]);
  const [editUserToAdd, setEditUserToAdd] = useState("");
  const [editSchoolToAdd, setEditSchoolToAdd] = useState("");
  const [editUserRefs, setEditUserRefs] = useState({});
  const [editSchoolRefs, setEditSchoolRefs] = useState({});

  async function loadStudents() {
    if (!selectedSchoolId) {
      return;
    }
    try {
      const query = new URLSearchParams({ offset: String(offset), limit: String(DEFAULT_LIMIT) });
      if (search.trim()) {
        query.set("search", search.trim());
      }
      const payload = await request(`/api/v1/students?${query.toString()}`);
      setRows(payload.items ?? []);
      setPagination(payload.pagination ?? null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadAssociationOptions() {
    if (!selectedSchoolId) {
      return;
    }
    try {
      const [usersPayload, schoolsPayload] = await Promise.all([
        request("/api/v1/users?offset=0&limit=100"),
        request("/api/v1/schools?offset=0&limit=100"),
      ]);
      setUserOptions(usersPayload.items ?? []);
      setSchoolOptions(schoolsPayload.items ?? []);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    setOffset(0);
  }, [search, selectedSchoolId]);

  useEffect(() => {
    loadAssociationOptions();
  }, [selectedSchoolId]);

  useEffect(() => {
    loadStudents();
  }, [offset, selectedSchoolId, search]);

  useEffect(() => {
    if (!createOpen) {
      return;
    }
    setCreateSelectedSchoolIds(selectedSchoolId ? [Number(selectedSchoolId)] : []);
  }, [createOpen, selectedSchoolId]);

  function userLabel(userId) {
    const user = userOptions.find((item) => item.id === userId);
    if (!user) {
      return `User #${userId}`;
    }
    const firstName = user.profile?.first_name ?? "";
    const lastName = user.profile?.last_name ?? "";
    const fullName = `${firstName} ${lastName}`.trim();
    return fullName ? `${fullName} (${user.email})` : user.email;
  }

  function schoolLabel(schoolId) {
    const school = schoolOptions.find((item) => item.id === schoolId);
    return school ? school.name : `School #${schoolId}`;
  }

  function userLabelForEdit(userId) {
    const ref = editUserRefs[userId];
    if (ref) {
      return `${ref.name} (${ref.email})`;
    }
    return userLabel(userId);
  }

  function schoolLabelForEdit(schoolId) {
    const ref = editSchoolRefs[schoolId];
    if (ref) {
      return ref.name;
    }
    return schoolLabel(schoolId);
  }

  function openEdit(student) {
    setEditStudent(student);
    setEditForm({
      first_name: student.first_name ?? "",
      last_name: student.last_name ?? "",
      external_id: student.external_id ?? "",
    });
    const studentUserIds = student.user_ids ?? [];
    const studentSchoolIds = student.school_ids ?? [];
    const userRefs = Object.fromEntries((student.users ?? []).map((user) => [user.id, user]));
    const schoolRefs = Object.fromEntries((student.schools ?? []).map((school) => [school.id, school]));
    setEditSelectedUserIds(studentUserIds);
    setEditSelectedSchoolIds(studentSchoolIds);
    setEditInitialUserIds(studentUserIds);
    setEditInitialSchoolIds(studentSchoolIds);
    setEditUserRefs(userRefs);
    setEditSchoolRefs(schoolRefs);
  }

  return (
    <section className="page-card">
      <SectionTitle>Students</SectionTitle>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      <TableToolbar
        search={search}
        onSearch={setSearch}
        onCreate={() => {
          setError("");
          setCreateOpen(true);
          setCreateSelectedUserIds([]);
          setCreateSelectedSchoolIds(selectedSchoolId ? [Number(selectedSchoolId)] : []);
          setCreateUserToAdd("");
          setCreateSchoolToAdd("");
        }}
      />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>First name</th>
            <th>Last name</th>
            <th>External ID</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <NavLink className="ghost action-link" to={`/students/${row.id}`}>
                  {row.id}
                </NavLink>
              </td>
              <td>{row.first_name}</td>
              <td>{row.last_name}</td>
              <td>{row.external_id ?? "-"}</td>
              <td className="row-actions">
                <button className="ghost" onClick={() => openEdit(row)} type="button">
                  Edit
                </button>
                <button className="danger" onClick={() => setDeleteStudent(row)} type="button">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <PaginationControls pagination={pagination} onChange={setOffset} />

      {createOpen && (
        <Modal
          title="Create student"
          onClose={() => setCreateOpen(false)}
          onSubmit={async () => {
            try {
              const createdStudent = await request("/api/v1/students", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  first_name: createForm.first_name,
                  last_name: createForm.last_name,
                  external_id: createForm.external_id || null,
                }),
              });
              for (const userId of createSelectedUserIds) {
                await request(`/api/v1/students/${createdStudent.id}/users`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ user_id: userId }),
                });
              }
              const currentSchoolId = Number(selectedSchoolId);
              for (const schoolId of createSelectedSchoolIds) {
                if (schoolId === currentSchoolId) {
                  continue;
                }
                await request(`/api/v1/students/${createdStudent.id}/schools`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ school_id: schoolId }),
                });
              }
              if (selectedSchoolId && !createSelectedSchoolIds.includes(Number(selectedSchoolId))) {
                await request(`/api/v1/students/${createdStudent.id}/schools/${Number(selectedSchoolId)}`, {
                  method: "DELETE",
                });
              }
              setCreateOpen(false);
              setCreateForm({ first_name: "", last_name: "", external_id: "" });
              setCreateSelectedUserIds([]);
              setCreateSelectedSchoolIds([]);
              setCreateUserToAdd("");
              setCreateSchoolToAdd("");
              setMessage("Student created");
              await loadStudents();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Create"
        >
          <input
            placeholder="First name"
            value={createForm.first_name}
            onChange={(e) => setCreateForm({ ...createForm, first_name: e.target.value })}
          />
          <input
            placeholder="Last name"
            value={createForm.last_name}
            onChange={(e) => setCreateForm({ ...createForm, last_name: e.target.value })}
          />
          <input
            placeholder="External id"
            value={createForm.external_id}
            onChange={(e) => setCreateForm({ ...createForm, external_id: e.target.value })}
          />
          <div className="association-box">
            <p className="muted">Associated users</p>
            <div className="association-row">
              <select value={createUserToAdd} onChange={(e) => setCreateUserToAdd(e.target.value)}>
                <option value="">Select user</option>
                {userOptions
                  .filter((user) => !createSelectedUserIds.includes(user.id))
                  .map((user) => (
                    <option key={user.id} value={user.id}>
                      {userLabel(user.id)}
                    </option>
                  ))}
              </select>
              <button
                className="ghost"
                type="button"
                onClick={() => {
                  const id = Number(createUserToAdd);
                  if (!id || createSelectedUserIds.includes(id)) {
                    return;
                  }
                  setCreateSelectedUserIds([...createSelectedUserIds, id]);
                  setCreateUserToAdd("");
                }}
              >
                Add
              </button>
            </div>
            <div className="chips">
              {createSelectedUserIds.map((userId) => (
                <span className="chip" key={userId}>
                  {userLabel(userId)}
                  <button
                    className="chip-remove"
                    onClick={() => setCreateSelectedUserIds(createSelectedUserIds.filter((id) => id !== userId))}
                    type="button"
                  >
                    x
                  </button>
                </span>
              ))}
            </div>
          </div>
          <div className="association-box">
            <p className="muted">Associated schools</p>
            <div className="association-row">
              <select value={createSchoolToAdd} onChange={(e) => setCreateSchoolToAdd(e.target.value)}>
                <option value="">Select school</option>
                {schoolOptions
                  .filter((school) => !createSelectedSchoolIds.includes(school.id))
                  .map((school) => (
                    <option key={school.id} value={school.id}>
                      {school.name}
                    </option>
                  ))}
              </select>
              <button
                className="ghost"
                type="button"
                onClick={() => {
                  const id = Number(createSchoolToAdd);
                  if (!id || createSelectedSchoolIds.includes(id)) {
                    return;
                  }
                  setCreateSelectedSchoolIds([...createSelectedSchoolIds, id]);
                  setCreateSchoolToAdd("");
                }}
              >
                Add
              </button>
            </div>
            <div className="chips">
              {createSelectedSchoolIds.map((schoolId) => (
                <span className="chip" key={schoolId}>
                  {schoolLabel(schoolId)}
                  <button
                    className="chip-remove"
                    onClick={() => setCreateSelectedSchoolIds(createSelectedSchoolIds.filter((id) => id !== schoolId))}
                    type="button"
                  >
                    x
                  </button>
                </span>
              ))}
            </div>
          </div>
        </Modal>
      )}

      {editStudent && (
        <Modal
          title={`Edit student #${editStudent.id}`}
          onClose={() => setEditStudent(null)}
          onSubmit={async () => {
            try {
              const usersToAdd = editSelectedUserIds.filter((id) => !editInitialUserIds.includes(id));
              const usersToRemove = editInitialUserIds.filter((id) => !editSelectedUserIds.includes(id));
              const schoolsToAdd = editSelectedSchoolIds.filter((id) => !editInitialSchoolIds.includes(id));
              const schoolsToRemove = editInitialSchoolIds.filter((id) => !editSelectedSchoolIds.includes(id));
              await request(`/api/v1/students/${editStudent.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  first_name: editForm.first_name || undefined,
                  last_name: editForm.last_name || undefined,
                  external_id: editForm.external_id || undefined,
                  associations: {
                    add: { user_ids: usersToAdd, school_ids: schoolsToAdd },
                    remove: { user_ids: usersToRemove, school_ids: schoolsToRemove },
                  },
                }),
              });
              setEditStudent(null);
              setEditSelectedUserIds([]);
              setEditSelectedSchoolIds([]);
              setEditInitialUserIds([]);
              setEditInitialSchoolIds([]);
              setEditUserToAdd("");
              setEditSchoolToAdd("");
              setEditUserRefs({});
              setEditSchoolRefs({});
              setMessage("Student updated");
              await loadStudents();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Update"
        >
          <input
            placeholder="First name"
            value={editForm.first_name}
            onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
          />
          <input
            placeholder="Last name"
            value={editForm.last_name}
            onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
          />
          <input
            placeholder="External id"
            value={editForm.external_id}
            onChange={(e) => setEditForm({ ...editForm, external_id: e.target.value })}
          />
          <div className="association-box">
            <p className="muted">Associated users</p>
            <div className="association-row">
              <select value={editUserToAdd} onChange={(e) => setEditUserToAdd(e.target.value)}>
                <option value="">Select user</option>
                {userOptions
                  .filter((user) => !editSelectedUserIds.includes(user.id))
                  .map((user) => (
                    <option key={user.id} value={user.id}>
                      {userLabel(user.id)}
                    </option>
                  ))}
              </select>
              <button
                className="ghost"
                type="button"
                onClick={() => {
                  const id = Number(editUserToAdd);
                  if (!id || editSelectedUserIds.includes(id)) {
                    return;
                  }
                  setEditSelectedUserIds([...editSelectedUserIds, id]);
                  setEditUserToAdd("");
                }}
              >
                Add
              </button>
            </div>
            <div className="chips">
              {editSelectedUserIds.map((userId) => (
                <span className="chip" key={userId}>
                  {userLabelForEdit(userId)}
                  <button
                    className="chip-remove"
                    onClick={() => setEditSelectedUserIds(editSelectedUserIds.filter((id) => id !== userId))}
                    type="button"
                  >
                    x
                  </button>
                </span>
              ))}
            </div>
          </div>
          <div className="association-box">
            <p className="muted">Associated schools</p>
            <div className="association-row">
              <select value={editSchoolToAdd} onChange={(e) => setEditSchoolToAdd(e.target.value)}>
                <option value="">Select school</option>
                {schoolOptions
                  .filter((school) => !editSelectedSchoolIds.includes(school.id))
                  .map((school) => (
                    <option key={school.id} value={school.id}>
                      {school.name}
                    </option>
                  ))}
              </select>
              <button
                className="ghost"
                type="button"
                onClick={() => {
                  const id = Number(editSchoolToAdd);
                  if (!id || editSelectedSchoolIds.includes(id)) {
                    return;
                  }
                  setEditSelectedSchoolIds([...editSelectedSchoolIds, id]);
                  setEditSchoolToAdd("");
                }}
              >
                Add
              </button>
            </div>
            <div className="chips">
              {editSelectedSchoolIds.map((schoolId) => (
                <span className="chip" key={schoolId}>
                  {schoolLabelForEdit(schoolId)}
                  <button
                    className="chip-remove"
                    onClick={() => setEditSelectedSchoolIds(editSelectedSchoolIds.filter((id) => id !== schoolId))}
                    type="button"
                  >
                    x
                  </button>
                </span>
              ))}
            </div>
          </div>
        </Modal>
      )}

      {deleteStudent && (
        <Modal
          danger
          title={`Delete student #${deleteStudent.id}?`}
          onClose={() => setDeleteStudent(null)}
          onSubmit={async () => {
            try {
              await request(`/api/v1/students/${deleteStudent.id}`, { method: "DELETE" });
              setDeleteStudent(null);
              setMessage("Student deleted");
              await loadStudents();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Delete"
        >
          <p>This action cannot be undone.</p>
        </Modal>
      )}
    </section>
  );
}

function SchoolsConfigPage({ request, selectedSchoolId }) {
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editSchool, setEditSchool] = useState(null);
  const [deleteSchool, setDeleteSchool] = useState(null);
  const [createForm, setCreateForm] = useState({ name: "", slug: "" });
  const [editForm, setEditForm] = useState({ name: "", slug: "", is_active: "true" });

  async function loadSchools() {
    try {
      const query = new URLSearchParams({ offset: String(offset), limit: String(DEFAULT_LIMIT) });
      if (search.trim()) {
        query.set("search", search.trim());
      }
      const payload = await request(`/api/v1/schools?${query.toString()}`);
      setRows(payload.items ?? []);
      setPagination(payload.pagination ?? null);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    setOffset(0);
  }, [search, selectedSchoolId]);

  useEffect(() => {
    loadSchools();
  }, [offset, selectedSchoolId, search]);

  function openEdit(school) {
    setEditSchool(school);
    setEditForm({ name: school.name ?? "", slug: school.slug ?? "", is_active: String(school.is_active ?? true) });
  }

  return (
    <section className="page-card">
      <SectionTitle>Schools</SectionTitle>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      <TableToolbar
        search={search}
        onSearch={setSearch}
        onCreate={() => {
          setError("");
          setCreateOpen(true);
          setCreateForm({
            student_id: "",
            fee_definition_id: "",
            description: "",
            amount: "",
            period: "",
            debt_created_at: currentDateTimeLocal(),
            due_date: "",
            charge_type: "fee",
            status: "unpaid",
          });
        }}
      />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Slug</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{row.name}</td>
              <td>{row.slug}</td>
              <td>{row.is_active ? "yes" : "no"}</td>
              <td className="row-actions">
                <button className="ghost" onClick={() => openEdit(row)} type="button">
                  Edit
                </button>
                <button className="danger" onClick={() => setDeleteSchool(row)} type="button">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <PaginationControls pagination={pagination} onChange={setOffset} />

      {createOpen && (
        <Modal
          title="Create school"
          onClose={() => setCreateOpen(false)}
          onSubmit={async () => {
            try {
              await request("/api/v1/schools", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: createForm.name, slug: createForm.slug }),
              });
              setCreateOpen(false);
              setCreateForm({ name: "", slug: "" });
              setMessage("School created");
              await loadSchools();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Create"
        >
          <input placeholder="Name" value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} />
          <input placeholder="Slug" value={createForm.slug} onChange={(e) => setCreateForm({ ...createForm, slug: e.target.value })} />
        </Modal>
      )}

      {editSchool && (
        <Modal
          title={`Edit school #${editSchool.id}`}
          onClose={() => setEditSchool(null)}
          onSubmit={async () => {
            try {
              await request(
                `/api/v1/schools/${editSchool.id}`,
                {
                  method: "PUT",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    name: editForm.name || undefined,
                    slug: editForm.slug || undefined,
                    is_active: editForm.is_active === "true",
                  }),
                },
                editSchool.id,
              );
              setEditSchool(null);
              setMessage("School updated");
              await loadSchools();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Update"
        >
          <input placeholder="Name" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
          <input placeholder="Slug" value={editForm.slug} onChange={(e) => setEditForm({ ...editForm, slug: e.target.value })} />
          <select value={editForm.is_active} onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value })}>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </Modal>
      )}

      {deleteSchool && (
        <Modal
          danger
          title={`Delete school #${deleteSchool.id}?`}
          onClose={() => setDeleteSchool(null)}
          onSubmit={async () => {
            try {
              await request(`/api/v1/schools/${deleteSchool.id}`, { method: "DELETE" }, deleteSchool.id);
              setDeleteSchool(null);
              setMessage("School deleted");
              await loadSchools();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Delete"
        >
          <p>This action cannot be undone.</p>
        </Modal>
      )}
    </section>
  );
}

function FeesConfigPage({ request, selectedSchoolId }) {
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editFee, setEditFee] = useState(null);
  const [deleteFee, setDeleteFee] = useState(null);
  const [createForm, setCreateForm] = useState({ name: "", amount: "", recurrence: "monthly", is_active: "true" });
  const [editForm, setEditForm] = useState({ name: "", amount: "", recurrence: "monthly", is_active: "true" });

  async function loadFees() {
    if (!selectedSchoolId) {
      return;
    }
    try {
      const query = new URLSearchParams({ offset: String(offset), limit: String(DEFAULT_LIMIT) });
      if (search.trim()) {
        query.set("search", search.trim());
      }
      const payload = await request(`/api/v1/fees?${query.toString()}`);
      setRows(payload.items ?? []);
      setPagination(payload.pagination ?? null);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    setOffset(0);
  }, [search, selectedSchoolId]);

  useEffect(() => {
    loadFees();
  }, [offset, selectedSchoolId, search]);

  function openEdit(fee) {
    setEditFee(fee);
    setEditForm({
      name: fee.name ?? "",
      amount: fee.amount != null ? String(fee.amount) : "",
      recurrence: fee.recurrence ?? "monthly",
      is_active: String(fee.is_active ?? true),
    });
  }

  return (
    <section className="page-card">
      <SectionTitle>Fees</SectionTitle>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      <TableToolbar
        search={search}
        onSearch={setSearch}
        onCreate={() => {
          setError("");
          setCreateOpen(true);
        }}
      />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Amount</th>
            <th>Recurrence</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{row.name}</td>
              <td>{formatCurrency(row.amount)}</td>
              <td>{row.recurrence}</td>
              <td>{row.is_active ? "yes" : "no"}</td>
              <td className="row-actions">
                <button className="ghost" onClick={() => openEdit(row)} type="button">
                  Edit
                </button>
                <button className="danger" onClick={() => setDeleteFee(row)} type="button">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <PaginationControls pagination={pagination} onChange={setOffset} />

      {createOpen && (
        <Modal
          title="Create fee"
          onClose={() => setCreateOpen(false)}
          onSubmit={async () => {
            try {
              await request("/api/v1/fees", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  name: createForm.name,
                  amount: createForm.amount,
                  recurrence: createForm.recurrence,
                  is_active: createForm.is_active === "true",
                }),
              });
              setCreateOpen(false);
              setCreateForm({ name: "", amount: "", recurrence: "monthly", is_active: "true" });
              setMessage("Fee created");
              await loadFees();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Create"
        >
          <input placeholder="Name" value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} />
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            value={createForm.amount}
            onChange={(e) => setCreateForm({ ...createForm, amount: e.target.value })}
          />
          <select value={createForm.recurrence} onChange={(e) => setCreateForm({ ...createForm, recurrence: e.target.value })}>
            {FEE_RECURRENCE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select value={createForm.is_active} onChange={(e) => setCreateForm({ ...createForm, is_active: e.target.value })}>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </Modal>
      )}

      {editFee && (
        <Modal
          title={`Edit fee #${editFee.id}`}
          onClose={() => setEditFee(null)}
          onSubmit={async () => {
            try {
              await request(`/api/v1/fees/${editFee.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  name: editForm.name || undefined,
                  amount: editForm.amount || undefined,
                  recurrence: editForm.recurrence || undefined,
                  is_active: editForm.is_active === "true",
                }),
              });
              setEditFee(null);
              setMessage("Fee updated");
              await loadFees();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Update"
        >
          <input placeholder="Name" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            value={editForm.amount}
            onChange={(e) => setEditForm({ ...editForm, amount: e.target.value })}
          />
          <select value={editForm.recurrence} onChange={(e) => setEditForm({ ...editForm, recurrence: e.target.value })}>
            {FEE_RECURRENCE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select value={editForm.is_active} onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value })}>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </Modal>
      )}

      {deleteFee && (
        <Modal
          danger
          title={`Delete fee #${deleteFee.id}?`}
          onClose={() => setDeleteFee(null)}
          onSubmit={async () => {
            try {
              await request(`/api/v1/fees/${deleteFee.id}`, { method: "DELETE" });
              setDeleteFee(null);
              setMessage("Fee deleted");
              await loadFees();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Delete"
        >
          <p>This action cannot be undone.</p>
        </Modal>
      )}
    </section>
  );
}

function ChargesConfigPage({ request, selectedSchoolId }) {
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editCharge, setEditCharge] = useState(null);
  const [deleteCharge, setDeleteCharge] = useState(null);
  const [studentOptions, setStudentOptions] = useState([]);
  const [feeOptions, setFeeOptions] = useState([]);
  const [createForm, setCreateForm] = useState({
    student_id: "",
    fee_definition_id: "",
    description: "",
    amount: "",
    period: "",
    debt_created_at: "",
    due_date: "",
    charge_type: "fee",
    status: "unpaid",
  });
  const [editForm, setEditForm] = useState({
    student_id: "",
    fee_definition_id: "",
    description: "",
    amount: "",
    period: "",
    debt_created_at: "",
    due_date: "",
    charge_type: "fee",
    status: "unpaid",
  });

  async function loadCharges() {
    if (!selectedSchoolId) {
      return;
    }
    try {
      const query = new URLSearchParams({ offset: String(offset), limit: String(DEFAULT_LIMIT) });
      if (search.trim()) {
        query.set("search", search.trim());
      }
      const payload = await request(`/api/v1/charges?${query.toString()}`);
      setRows(payload.items ?? []);
      setPagination(payload.pagination ?? null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadAssociationOptions() {
    if (!selectedSchoolId) {
      return;
    }
    try {
      const [studentsPayload, feesPayload] = await Promise.all([
        request("/api/v1/students?offset=0&limit=100"),
        request("/api/v1/fees?offset=0&limit=100"),
      ]);
      setStudentOptions(studentsPayload.items ?? []);
      setFeeOptions(feesPayload.items ?? []);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    setOffset(0);
  }, [search, selectedSchoolId]);

  useEffect(() => {
    loadAssociationOptions();
  }, [selectedSchoolId]);

  useEffect(() => {
    loadCharges();
  }, [offset, selectedSchoolId, search]);

  function openEdit(charge) {
    setEditCharge(charge);
    setEditForm({
      student_id: charge.student_id != null ? String(charge.student_id) : "",
      fee_definition_id: charge.fee_definition_id != null ? String(charge.fee_definition_id) : "",
      description: charge.description ?? "",
      amount: charge.amount != null ? String(charge.amount) : "",
      period: charge.period ?? "",
      debt_created_at: toDateTimeLocal(charge.debt_created_at),
      due_date: charge.due_date ?? "",
      charge_type: charge.charge_type ?? "fee",
      status: charge.status ?? "unpaid",
    });
  }

  function studentLabel(student) {
    return `${student.first_name} ${student.last_name}`.trim();
  }

  return (
    <section className="page-card">
      <SectionTitle>Charges</SectionTitle>
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}
      <TableToolbar
        search={search}
        onSearch={setSearch}
        onCreate={() => {
          setError("");
          setCreateOpen(true);
        }}
      />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Student</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Due date</th>
            <th>Type</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{row.student ? `${row.student.first_name} ${row.student.last_name}` : `Student #${row.student_id}`}</td>
              <td>{row.description}</td>
              <td>{formatCurrency(row.amount)}</td>
              <td>{row.due_date}</td>
              <td>{row.charge_type}</td>
              <td>{row.status}</td>
              <td className="row-actions">
                <button className="ghost" onClick={() => openEdit(row)} type="button">
                  Edit
                </button>
                <button className="danger" onClick={() => setDeleteCharge(row)} type="button">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <PaginationControls pagination={pagination} onChange={setOffset} />

      {createOpen && (
        <Modal
          title="Create charge"
          onClose={() => setCreateOpen(false)}
          onSubmit={async () => {
            try {
              await request("/api/v1/charges", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  student_id: Number(createForm.student_id),
                  fee_definition_id: createForm.fee_definition_id ? Number(createForm.fee_definition_id) : null,
                  description: createForm.description,
                  amount: createForm.amount,
                  period: createForm.period || null,
                  debt_created_at: createForm.debt_created_at ? new Date(createForm.debt_created_at).toISOString() : undefined,
                  due_date: createForm.due_date,
                  charge_type: createForm.charge_type,
                  status: createForm.status,
                }),
              });
              setCreateOpen(false);
              setCreateForm({
                student_id: "",
                fee_definition_id: "",
                description: "",
                amount: "",
                period: "",
                debt_created_at: currentDateTimeLocal(),
                due_date: "",
                charge_type: "fee",
                status: "unpaid",
              });
              setMessage("Charge created");
              await loadCharges();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Create"
        >
          <select value={createForm.student_id} onChange={(e) => setCreateForm({ ...createForm, student_id: e.target.value })}>
            <option value="">Select student</option>
            {studentOptions.map((student) => (
              <option key={student.id} value={student.id}>
                {studentLabel(student)}
              </option>
            ))}
          </select>
          <select value={createForm.fee_definition_id} onChange={(e) => setCreateForm({ ...createForm, fee_definition_id: e.target.value })}>
            <option value="">No fee definition</option>
            {feeOptions.map((fee) => (
              <option key={fee.id} value={fee.id}>
                {fee.name}
              </option>
            ))}
          </select>
          <input
            placeholder="Description"
            value={createForm.description}
            onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            value={createForm.amount}
            onChange={(e) => setCreateForm({ ...createForm, amount: e.target.value })}
          />
          <input placeholder="Period (YYYY-MM)" value={createForm.period} onChange={(e) => setCreateForm({ ...createForm, period: e.target.value })} />
          <input
            type="datetime-local"
            value={createForm.debt_created_at}
            onChange={(e) => setCreateForm({ ...createForm, debt_created_at: e.target.value })}
          />
          <input type="date" value={createForm.due_date} onChange={(e) => setCreateForm({ ...createForm, due_date: e.target.value })} />
          <select value={createForm.charge_type} onChange={(e) => setCreateForm({ ...createForm, charge_type: e.target.value })}>
            {CHARGE_TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select value={createForm.status} onChange={(e) => setCreateForm({ ...createForm, status: e.target.value })}>
            {CHARGE_STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </Modal>
      )}

      {editCharge && (
        <Modal
          title={`Edit charge #${editCharge.id}`}
          onClose={() => setEditCharge(null)}
          onSubmit={async () => {
            try {
              await request(`/api/v1/charges/${editCharge.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  student_id: editForm.student_id ? Number(editForm.student_id) : undefined,
                  fee_definition_id: editForm.fee_definition_id ? Number(editForm.fee_definition_id) : null,
                  description: editForm.description || undefined,
                  amount: editForm.amount || undefined,
                  period: editForm.period || null,
                  debt_created_at: editForm.debt_created_at ? new Date(editForm.debt_created_at).toISOString() : undefined,
                  due_date: editForm.due_date || undefined,
                  charge_type: editForm.charge_type || undefined,
                  status: editForm.status || undefined,
                }),
              });
              setEditCharge(null);
              setMessage("Charge updated");
              await loadCharges();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Update"
        >
          <select value={editForm.student_id} onChange={(e) => setEditForm({ ...editForm, student_id: e.target.value })}>
            <option value="">Select student</option>
            {studentOptions.map((student) => (
              <option key={student.id} value={student.id}>
                {studentLabel(student)}
              </option>
            ))}
          </select>
          <select value={editForm.fee_definition_id} onChange={(e) => setEditForm({ ...editForm, fee_definition_id: e.target.value })}>
            <option value="">No fee definition</option>
            {feeOptions.map((fee) => (
              <option key={fee.id} value={fee.id}>
                {fee.name}
              </option>
            ))}
          </select>
          <input placeholder="Description" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} />
          <input type="number" step="0.01" placeholder="Amount" value={editForm.amount} onChange={(e) => setEditForm({ ...editForm, amount: e.target.value })} />
          <input placeholder="Period (YYYY-MM)" value={editForm.period} onChange={(e) => setEditForm({ ...editForm, period: e.target.value })} />
          <input
            type="datetime-local"
            value={editForm.debt_created_at}
            onChange={(e) => setEditForm({ ...editForm, debt_created_at: e.target.value })}
          />
          <input type="date" value={editForm.due_date} onChange={(e) => setEditForm({ ...editForm, due_date: e.target.value })} />
          <select value={editForm.charge_type} onChange={(e) => setEditForm({ ...editForm, charge_type: e.target.value })}>
            {CHARGE_TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}>
            {CHARGE_STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </Modal>
      )}

      {deleteCharge && (
        <Modal
          danger
          title={`Delete charge #${deleteCharge.id}?`}
          onClose={() => setDeleteCharge(null)}
          onSubmit={async () => {
            try {
              await request(`/api/v1/charges/${deleteCharge.id}`, { method: "DELETE" });
              setDeleteCharge(null);
              setMessage("Charge deleted");
              await loadCharges();
            } catch (err) {
              setError(err.message);
            }
          }}
          submitLabel="Delete"
        >
          <p>This action cannot be undone.</p>
        </Modal>
      )}
    </section>
  );
}

function Sidebar({ isSchoolAdmin, myStudents, selectedSchoolId }) {
  return (
    <aside className="sidebar">
      <h2 className="sidebar-title">Mattilda</h2>
      <nav className="sidebar-nav">
        <NavLink to="/dashboard">Dashboard</NavLink>

        {isSchoolAdmin && (
          <div className="sidebar-group">
            <p>Configuration</p>
            <NavLink to="/config/users">Users</NavLink>
            <NavLink to="/config/students">Students</NavLink>
            <NavLink to="/config/schools">Schools</NavLink>
            <NavLink to="/config/fees">Fees</NavLink>
            <NavLink to="/config/charges">Charges</NavLink>
          </div>
        )}

        <div className="sidebar-group">
          <p>Students</p>
          {myStudents.length === 0 && <span className="muted">No students</span>}
          {myStudents.map((student) => (
            <NavLink key={student.id} to={`/students/${student.id}`}>
              {student.first_name} {student.last_name}
            </NavLink>
          ))}
        </div>

        {!selectedSchoolId && <p className="muted">Select a school to continue.</p>}
      </nav>
    </aside>
  );
}

function AppLayout({
  me,
  selectedSchoolId,
  setSelectedSchoolId,
  selectedSchool,
  activeSchool,
  schoolFinancialSummary,
  onLogout,
  isSchoolAdmin,
  myStudents,
  request,
}) {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (location.pathname === "/") {
      navigate("/dashboard", { replace: true });
    }
  }, [location.pathname, navigate]);

  return (
    <div className="app-shell">
      <Sidebar isSchoolAdmin={isSchoolAdmin} myStudents={myStudents} selectedSchoolId={selectedSchoolId} />
      <main className="content">
        <header className="topbar">
          <div>
            <strong>{activeSchool?.name ?? "No school selected"}</strong>
          </div>
          <div className="topbar-actions">
            <select
              value={selectedSchoolId}
              onChange={(event) => {
                const next = event.target.value;
                setSelectedSchoolId(next);
                if (next) {
                  localStorage.setItem(SCHOOL_KEY, next);
                } else {
                  localStorage.removeItem(SCHOOL_KEY);
                }
                navigate("/dashboard");
              }}
            >
              {(me?.schools ?? []).map((school) => (
                <option key={school.school_id} value={school.school_id}>
                  {school.school_name}
                </option>
              ))}
            </select>
            <NavLink className="avatar-link" to="/profile">
              {me?.profile?.first_name?.slice(0, 1) ?? "U"}
            </NavLink>
            <button className="ghost" onClick={onLogout} type="button">
              Logout
            </button>
          </div>
        </header>

        <Routes>
          <Route
            path="/dashboard"
            element={<DashboardPage activeSchool={activeSchool} isSchoolAdmin={isSchoolAdmin} schoolFinancialSummary={schoolFinancialSummary} />}
          />
          <Route path="/profile" element={<ProfilePage me={me} selectedSchool={selectedSchool} />} />
          <Route
            path="/students/:studentId"
            element={<StudentDetailPage selectedSchoolId={selectedSchoolId} request={request} isSchoolAdmin={isSchoolAdmin} />}
          />
          <Route
            path="/students/:studentId/billing"
            element={<StudentDetailPage selectedSchoolId={selectedSchoolId} request={request} isSchoolAdmin={isSchoolAdmin} />}
          />
          <Route
            path="/students/:studentId/payments"
            element={<StudentDetailPage selectedSchoolId={selectedSchoolId} request={request} isSchoolAdmin={isSchoolAdmin} />}
          />
          <Route
            path="/students/:studentId/billing/:invoiceId"
            element={<InvoiceDetailPage selectedSchoolId={selectedSchoolId} request={request} />}
          />
          <Route
            path="/config/users"
            element={isSchoolAdmin ? <UsersConfigPage request={request} selectedSchoolId={selectedSchoolId} /> : <Navigate replace to="/dashboard" />}
          />
          <Route
            path="/config/students"
            element={
              isSchoolAdmin ? <StudentsConfigPage request={request} selectedSchoolId={selectedSchoolId} /> : <Navigate replace to="/dashboard" />
            }
          />
          <Route
            path="/config/schools"
            element={isSchoolAdmin ? <SchoolsConfigPage request={request} selectedSchoolId={selectedSchoolId} /> : <Navigate replace to="/dashboard" />}
          />
          <Route
            path="/config/fees"
            element={isSchoolAdmin ? <FeesConfigPage request={request} selectedSchoolId={selectedSchoolId} /> : <Navigate replace to="/dashboard" />}
          />
          <Route
            path="/config/charges"
            element={isSchoolAdmin ? <ChargesConfigPage request={request} selectedSchoolId={selectedSchoolId} /> : <Navigate replace to="/dashboard" />}
          />
          <Route path="*" element={<Navigate replace to="/dashboard" />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const navigate = useNavigate();
  const health = usePublicHealth();
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [selectedSchoolId, setSelectedSchoolId] = useState(() => localStorage.getItem(SCHOOL_KEY) ?? "");
  const [me, setMe] = useState(null);
  const [activeSchool, setActiveSchool] = useState(null);
  const [schoolFinancialSummary, setSchoolFinancialSummary] = useState(null);
  const [loadingAuth, setLoadingAuth] = useState(false);
  const [error, setError] = useState("");
  const [username, setUsername] = useState("admin@example.com");
  const [password, setPassword] = useState("admin123");

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

  const myStudents = useMemo(() => {
    if (!me || !selectedSchoolId) {
      return [];
    }
    return (me.students ?? []).filter((student) => student.school_ids.includes(Number(selectedSchoolId)));
  }, [me, selectedSchoolId]);

  async function authenticatedRequest(path, options = {}, schoolIdOverride = null) {
    if (!token) {
      throw new Error("Missing auth token");
    }
    const headers = {
      Authorization: `Bearer ${token}`,
      ...(options.headers ?? {}),
    };
    const schoolHeaderId = schoolIdOverride ?? selectedSchoolId;
    if (schoolHeaderId) {
      headers["X-School-Id"] = String(schoolHeaderId);
    }
    const response = await fetch(`${API_URL}${path}`, { ...options, headers });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
    }
    if (response.status === 204) {
      return null;
    }
    return response.json();
  }

  useEffect(() => {
    async function loadMe() {
      if (!token) {
        setMe(null);
        setActiveSchool(null);
        return;
      }
      setLoadingAuth(true);
      try {
        const mePayload = await authenticatedRequest("/api/v1/users/me");
        setMe(mePayload);
        if ((mePayload.schools ?? []).length === 0) {
          setSelectedSchoolId("");
          localStorage.removeItem(SCHOOL_KEY);
          return;
        }
        const selectedExists = mePayload.schools.some((school) => String(school.school_id) === String(selectedSchoolId));
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
        setSchoolFinancialSummary(null);
        return;
      }
      try {
        const payload = await authenticatedRequest(`/api/v1/schools/${selectedSchoolId}`);
        setActiveSchool(payload);
        if (isSchoolAdmin) {
          const summaryPayload = await authenticatedRequest(`/api/v1/schools/${selectedSchoolId}/financial-summary`);
          setSchoolFinancialSummary(summaryPayload);
        } else {
          setSchoolFinancialSummary(null);
        }
      } catch (_err) {
        setActiveSchool(null);
        setSchoolFinancialSummary(null);
      }
    }
    loadActiveSchool();
  }, [token, selectedSchoolId, me, isSchoolAdmin]);

  async function onLogin(event) {
    event.preventDefault();
    setError("");
    setLoadingAuth(true);
    try {
      const body = new URLSearchParams({ username, password });
      const response = await fetch(`${API_URL}/api/v1/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!response.ok) {
        throw new Error("Invalid credentials");
      }
      const data = await response.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      navigate("/dashboard");
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
    setSchoolFinancialSummary(null);
    navigate("/");
  }

  if (!token) {
    return (
      <LoginPage
        username={username}
        setUsername={setUsername}
        password={password}
        setPassword={setPassword}
        loading={loadingAuth}
        onSubmit={onLogin}
        error={error}
        health={health}
      />
    );
  }

  if (loadingAuth || !me) {
    return (
      <main className="loading-page">
        <p>Loading session...</p>
      </main>
    );
  }

  return (
    <AppLayout
      me={me}
      selectedSchoolId={selectedSchoolId}
      setSelectedSchoolId={setSelectedSchoolId}
      selectedSchool={selectedSchool}
      activeSchool={activeSchool}
      schoolFinancialSummary={schoolFinancialSummary}
      onLogout={onLogout}
      isSchoolAdmin={isSchoolAdmin}
      myStudents={myStudents}
      request={authenticatedRequest}
    />
  );
}

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { deleteReport, getReport } from "../api";

export default function DeleteRecord({ onDeleted }) {
  const { id } = useParams();
  const navigate = useNavigate();

  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    async function loadReport() {
      try {
        const data = await getReport(id);
        setReport(data);
      } catch (requestError) {
        const detail = requestError.response?.data?.detail;
        setError(detail || "Unable to load the report.");
      }
    }

    loadReport();
  }, [id]);

  async function handleDelete() {
    setError("");
    setBusy(true);

    try {
      await deleteReport(id);
      onDeleted(Number(id));
      navigate("/");
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      setError(detail || "Unable to delete the report.");
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <section className="card">
        <h2>Delete Report</h2>
        <p className="error">{error}</p>
      </section>
    );
  }

  if (!report) {
    return (
      <section className="card">
        <p>Loading report...</p>
      </section>
    );
  }

  return (
    <section className="card">
      <h2>Delete Vulnerability Report</h2>

      <p>
        Are you sure you want to delete report{" "}
        <strong>#{report.id}</strong> for{" "}
        <strong>{report.packageName}</strong>?
      </p>

      <p className="muted">
        Vulnerability ID: {report.vulnerabilityId}
      </p>

      {error && <p className="error">{error}</p>}

      <div className="actions">
        <button
          className="danger"
          onClick={handleDelete}
          disabled={busy}
        >
          {busy ? "Deleting..." : "Delete Report"}
        </button>

        <button
          className="secondary"
          onClick={() => navigate("/")}
          disabled={busy}
        >
          Cancel
        </button>
      </div>
    </section>
  );
}

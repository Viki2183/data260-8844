import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getReport } from "../api";


export default function UpdateRecord({ onUpdate }) {
  const { id } = useParams();

  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);


  useEffect(() => {
    async function loadReport() {
      try {
        const report = await getReport(id);

        setForm({
          packageName: report.packageName,
          packageId: report.packageId,
          vulnerabilityId: report.vulnerabilityId,
          submitterEmail: report.submitterEmail,
          vulnerabilityDescription:
            report.vulnerabilityDescription,
          severity: report.severity,
          affectedVersionsCount:
            report.affectedVersionsCount,
          termsAccepted: report.termsAccepted,
        });
      } catch (requestError) {
        const detail = requestError.response?.data?.detail;
        setError(detail || "Unable to load the report.");
      }
    }

    loadReport();
  }, [id]);


  function updateField(event) {
    const { name, value, type, checked } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: type === "checkbox" ? checked : value,
    }));
  }


  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);

    const payload = {
      ...form,
      packageId: Number(form.packageId),
      affectedVersionsCount: Number(
        form.affectedVersionsCount,
      ),
    };

    try {
      await onUpdate(id, payload);
    } catch (requestError) {
      const detail =
        requestError.response?.data?.detail ||
        (typeof requestError === "string"
          ? requestError
          : "Unable to update the vulnerability report.");

      setError(detail);
    } finally {
      setBusy(false);
    }
  }


  if (error && !form) {
    return (
      <section className="card">
        <h2>Update Report</h2>
        <p className="error">{error}</p>
      </section>
    );
  }


  if (!form) {
    return (
      <section className="card">
        <p>Loading report...</p>
      </section>
    );
  }


  return (
    <section className="card">
      <h2>Update Vulnerability Report</h2>

      <form onSubmit={handleSubmit} className="form">
        <label>
          Package name
          <input
            name="packageName"
            value={form.packageName}
            onChange={updateField}
            required
          />
        </label>

        <label>
          Package ID
          <input
            type="number"
            name="packageId"
            value={form.packageId}
            onChange={updateField}
            min="1"
            required
          />
        </label>

        <label>
          Vulnerability ID
          <input
            name="vulnerabilityId"
            value={form.vulnerabilityId}
            onChange={updateField}
            required
          />
        </label>

        <label>
          Submitter email
          <input
            type="email"
            name="submitterEmail"
            value={form.submitterEmail}
            onChange={updateField}
            required
          />
        </label>

        <label>
          Vulnerability description
          <textarea
            name="vulnerabilityDescription"
            value={form.vulnerabilityDescription}
            onChange={updateField}
            minLength={26}
            required
          />
        </label>

        <label>
          Severity
          <select
            name="severity"
            value={form.severity}
            onChange={updateField}
          >
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </label>

        <label>
          Affected versions count
          <input
            type="number"
            name="affectedVersionsCount"
            value={form.affectedVersionsCount}
            onChange={updateField}
            min="0"
            required
          />
        </label>

        <label className="checkbox-label">
          <input
            type="checkbox"
            name="termsAccepted"
            checked={form.termsAccepted}
            onChange={updateField}
            required
          />
          I accept the terms and conditions.
        </label>

        {error && <p className="error">{error}</p>}

        <button type="submit" disabled={busy}>
          {busy ? "Updating..." : "Update Vulnerability Report"}
        </button>
      </form>
    </section>
  );
}
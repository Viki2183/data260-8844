import { useState } from "react";


const initialForm = {
  packageName: "",
  packageId: "",
  vulnerabilityId: "",
  submitterEmail: "",
  vulnerabilityDescription: "",
  severity: "Medium",
  affectedVersionsCount: 0,
  termsAccepted: false,
};


export default function CreateRecord({ onCreate }) {
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);


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
      await onCreate(payload);
    } catch (requestError) {
      const detail =
        requestError.response?.data?.detail ||
        (typeof requestError === "string"
          ? requestError
          : "Unable to create the vulnerability report.");

      setError(detail);
    } finally {
      setBusy(false);
    }
  }


  return (
    <section className="card">
      <h2>Add Vulnerability Report</h2>

      <p className="muted">
        Enter the package and advisory information.
      </p>

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
          {busy ? "Saving..." : "Add Vulnerability Report"}
        </button>
      </form>
    </section>
  );
}
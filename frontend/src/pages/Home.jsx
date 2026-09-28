import { Link } from "react-router-dom";

export default function Home({ user, reports, loading, onLogout }) {
  if (!user) {
    return (
      <section className="card">
        <h2>Login required</h2>
        <p className="muted">
          Please log in before viewing or managing vulnerability reports.
        </p>

        <Link className="button" to="/login">
          Login
        </Link>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="page-header">
        <div>
          <h2>Vulnerability Reports</h2>
          <p className="muted">
            Logged in as {user.email}
          </p>
        </div>

        <div className="actions">
          <Link className="button" to="/create">
            Add Report
          </Link>

          <button className="button secondary" onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>

      {loading ? (
        <p>Loading reports...</p>
      ) : reports.length === 0 ? (
        <p className="muted">No vulnerability reports found.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Package</th>
                <th>Vulnerability ID</th>
                <th>Severity</th>
                <th>Submitter</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {reports.map((report) => (
                <tr key={report.id}>
                  <td>{report.id}</td>
                  <td>{report.packageName}</td>
                  <td>{report.vulnerabilityId}</td>
                  <td>{report.severity}</td>
                  <td>{report.submitterEmail}</td>
                  <td className="actions">
                    <Link
                      className="button small"
                      to={`/update/${report.id}`}
                    >
                      Update
                    </Link>

                    <Link
                      className="button danger small"
                      to={`/delete/${report.id}`}
                    >
                      Delete
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}


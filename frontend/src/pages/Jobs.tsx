import { useState } from "react";
import { api, IndexJob } from "../api";
import { Card, Empty, ErrorBox, Loading, StatusBadge } from "../components/ui";
import { formatDate } from "../format";
import { usePolling } from "../usePolling";

const ACTIVE = new Set(["queued", "running"]);

export default function Jobs() {
  const jobs = usePolling(api.jobs, 2000);
  const [actionError, setActionError] = useState<Error | null>(null);

  async function cancel(id: number) {
    setActionError(null);
    try {
      await api.cancelJob(id);
      jobs.refresh();
    } catch (e) {
      setActionError(e as Error);
    }
  }

  return (
    <div className="page">
      <h1>Jobs</h1>
      <p className="muted">
        Jobs run in the background and survive restarts: anything queued or running when the backend stops resumes
        on the next start.
      </p>
      <ErrorBox error={jobs.error ?? actionError} />
      <Card title="Recent jobs">
        {jobs.loading && !jobs.data ? (
          <Loading />
        ) : jobs.data && jobs.data.length === 0 ? (
          <Empty>No jobs yet. Start a scan from the Library page.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Type</th>
                  <th>Target</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Started</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {jobs.data?.map((j) => (
                  <tr key={j.id}>
                    <td>{j.id}</td>
                    <td>{j.job_type}</td>
                    <td className="mono small">{String(j.params.path ?? "")}</td>
                    <td>
                      <StatusBadge status={j.status} />
                      {j.error_message && <div className="small bad">{j.error_message}</div>}
                    </td>
                    <td>
                      <JobProgress job={j} />
                    </td>
                    <td className="small">{formatDate(j.started_at)}</td>
                    <td>
                      {ACTIVE.has(j.status) && (
                        <button className="secondary" disabled={j.cancel_requested} onClick={() => cancel(j.id)}>
                          {j.cancel_requested ? "Cancelling…" : "Cancel"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function JobProgress({ job }: { job: IndexJob }) {
  const r = job.result;
  if (job.job_type === "scan") {
    if (!r) return <span className="muted">{job.status === "running" ? "Walking folders…" : "—"}</span>;
    return (
      <span className="small">
        {r.discovered} found · {r.new} new · {r.changed} changed · {r.unchanged} unchanged
        {r.duplicates ? ` · ${r.duplicates} duplicate` : ""}
        {r.failed ? ` · ${r.failed} failed` : ""}
        {r.unsupported ? ` · ${r.unsupported} unsupported` : ""}
        {r.missing ? ` · ${r.missing} missing` : ""}
      </span>
    );
  }
  return <progress value={job.progress} max={1} />;
}

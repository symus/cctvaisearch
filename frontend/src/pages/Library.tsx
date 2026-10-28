import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api, IndexingStatus } from "../api";
import { Card, Empty, ErrorBox, Loading, StatusBadge } from "../components/ui";
import { formatBytes, formatDate, formatDuration } from "../format";
import { usePolling } from "../usePolling";

const PAGE = 50;
const STATUSES: IndexingStatus[] = ["pending", "indexing", "indexed", "failed", "unsupported", "missing"];

export default function Library() {
  const [path, setPath] = useState("");
  const [scanError, setScanError] = useState<Error | null>(null);
  const [scanMsg, setScanMsg] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);

  const folders = usePolling(api.folders, 5000);
  const videos = usePolling(() => api.videos({ q, status, limit: PAGE, offset }), 5000, [q, status, offset]);

  async function startScan(p: string) {
    setSubmitting(true);
    setScanError(null);
    setScanMsg(null);
    try {
      const job = await api.scan(p);
      setScanMsg(`Scan job #${job.id} queued. Progress is shown on the Jobs page.`);
      setPath("");
    } catch (e) {
      setScanError(e as Error);
    } finally {
      setSubmitting(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (path.trim()) startScan(path.trim());
  }

  return (
    <div className="page">
      <h1>Video library</h1>

      <Card title="Scan a folder">
        <form onSubmit={onSubmit} className="row">
          <label htmlFor="scan-path" className="sr-only">
            Folder path
          </label>
          <input
            id="scan-path"
            className="grow mono"
            placeholder="D:\CCTV\Exports"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
          <button type="submit" disabled={submitting || !path.trim()}>
            {submitting ? "Queuing…" : "Scan recursively"}
          </button>
        </form>
        <p className="muted small">
          Original files stay where they are; only metadata is stored. Unchanged files are skipped on re-scan.
        </p>
        <ErrorBox error={scanError} />
        {scanMsg && (
          <div className="ok">
            {scanMsg} <Link to="/jobs">Open jobs</Link>
          </div>
        )}
        {folders.data && folders.data.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Library folder</th>
                <th>Videos</th>
                <th>Last scanned</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {folders.data.map((f) => (
                <tr key={f.id}>
                  <td className="mono">{f.path}</td>
                  <td>{f.video_count}</td>
                  <td>{formatDate(f.last_scanned_at)}</td>
                  <td>
                    <button className="secondary" disabled={submitting} onClick={() => startScan(f.path)}>
                      Re-scan
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Videos">
        <div className="row">
          <input
            aria-label="Filter by filename"
            className="grow"
            placeholder="Filter by filename"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <ErrorBox error={videos.error} />
        {videos.loading && !videos.data ? (
          <Loading />
        ) : videos.data && videos.data.total === 0 ? (
          <Empty>{q || status ? "No videos match these filters." : "No videos yet. Scan a folder above."}</Empty>
        ) : videos.data ? (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Duration</th>
                    <th>Resolution</th>
                    <th>FPS</th>
                    <th>Codec</th>
                    <th>Size</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {videos.data.items.map((v) => (
                    <tr key={v.id}>
                      <td>
                        <div>{v.filename}</div>
                        <div className="muted small mono" title={v.path}>
                          #{v.id} · {v.path}
                        </div>
                        {v.duplicate_of_id && <div className="small warn">Duplicate of #{v.duplicate_of_id}</div>}
                        {v.error_message && <div className="small bad">{v.error_message}</div>}
                      </td>
                      <td>{formatDuration(v.duration_seconds)}</td>
                      <td>{v.width && v.height ? `${v.width}×${v.height}` : "—"}</td>
                      <td>{v.frame_rate ?? "—"}</td>
                      <td>{v.codec ?? "—"}</td>
                      <td>{formatBytes(v.size_bytes)}</td>
                      <td>
                        <StatusBadge status={v.indexing_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="row pager">
              <span className="muted">
                {offset + 1}–{Math.min(offset + PAGE, videos.data.total)} of {videos.data.total}
              </span>
              <button className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                Previous
              </button>
              <button
                className="secondary"
                disabled={offset + PAGE >= videos.data.total}
                onClick={() => setOffset(offset + PAGE)}
              >
                Next
              </button>
            </div>
          </>
        ) : null}
      </Card>
    </div>
  );
}

import { api } from "../api";
import { Card, ErrorBox, Loading } from "../components/ui";
import { formatBytes, formatDuration } from "../format";
import { usePolling } from "../usePolling";

export default function Dashboard() {
  const stats = usePolling(api.stats, 5000);
  const info = usePolling(api.systemInfo);
  const health = usePolling(api.health, 10000);

  return (
    <div className="page">
      <h1>Dashboard</h1>
      <ErrorBox error={stats.error ?? health.error} />

      {stats.loading && !stats.data ? (
        <Loading />
      ) : stats.data ? (
        <div className="tiles">
          <Tile label="Videos" value={stats.data.total_videos} />
          <Tile label="Pending" value={stats.data.by_status.pending} />
          <Tile label="Indexed" value={stats.data.by_status.indexed} />
          <Tile label="Failed / unsupported" value={stats.data.by_status.failed + stats.data.by_status.unsupported} />
          <Tile label="Missing" value={stats.data.by_status.missing} />
          <Tile label="Duplicates" value={stats.data.duplicates} />
          <Tile label="Footage" value={formatDuration(stats.data.total_duration_seconds)} />
          <Tile label="Detections" value={stats.data.total_detections} />
        </div>
      ) : null}

      <div className="grid2">
        <Card title="System">
          <ErrorBox error={info.error} />
          {info.data && (
            <dl className="kv">
              <dt>Backend</dt>
              <dd>
                {health.data ? `${health.data.status} · v${health.data.version} · schema ${health.data.schema_revision}` : "—"}
              </dd>
              <dt>OS</dt>
              <dd>{info.data.hardware.os}</dd>
              <dt>CPU</dt>
              <dd>
                {info.data.hardware.cpu} ({info.data.hardware.cpu_logical_cores} threads)
              </dd>
              <dt>RAM</dt>
              <dd>
                {formatBytes(info.data.hardware.ram_available_mb * 1048576)} free of{" "}
                {formatBytes(info.data.hardware.ram_total_mb * 1048576)}
              </dd>
              <dt>GPU</dt>
              <dd>{info.data.hardware.gpus.map((g) => g.name).join(", ") || "None detected"}</dd>
              <dt>Inference</dt>
              <dd>
                <strong>{info.data.hardware.inference_provider.toUpperCase()}</strong> —{" "}
                {info.data.hardware.inference_provider_reason}
              </dd>
              {info.data.hardware.tools.map((t) => (
                <div key={t.name} className="kv-row">
                  <dt>{t.name}</dt>
                  <dd className={t.available ? "" : "bad"}>
                    {t.available ? t.version : "Not found on PATH — install FFmpeg (see README)"}
                  </dd>
                </div>
              ))}
              <dt>Data folder</dt>
              <dd className="mono">{info.data.storage.data_dir}</dd>
              <dt>Disk free</dt>
              <dd>{formatBytes(info.data.storage.disk_free_bytes)}</dd>
            </dl>
          )}
        </Card>

        <Card title="AI models">
          {info.data && (
            <table>
              <tbody>
                {Object.entries(info.data.models).map(([name, m]) => (
                  <tr key={name}>
                    <td>{name.replace("_", " ")}</td>
                    <td>
                      <span className={`badge badge-${m.status}`}>{m.status.replace("_", " ")}</span>
                    </td>
                    <td className="muted">{m.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="muted small">
            Search results will be visual-similarity candidates for human review, never proof of identity.
          </p>
        </Card>
      </div>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="tile">
      <div className="tile-value">{value}</div>
      <div className="tile-label">{label}</div>
    </div>
  );
}

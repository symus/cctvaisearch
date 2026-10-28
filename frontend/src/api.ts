// Typed client for the local backend. All calls are same-origin (/api/...).

export type IndexingStatus = "pending" | "indexing" | "indexed" | "failed" | "unsupported" | "missing";
export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Health {
  status: string;
  version: string;
  database: string;
  schema_revision: string | null;
}

export interface Tool { name: string; available: boolean; path: string | null; version: string | null }
export interface Gpu { name: string; memory_mb: number | null; driver: string | null }

export interface SystemInfo {
  hardware: {
    os: string;
    python: string;
    cpu: string;
    cpu_logical_cores: number;
    ram_total_mb: number;
    ram_available_mb: number;
    gpus: Gpu[];
    inference_provider: string;
    inference_provider_reason: string;
    tools: Tool[];
  };
  storage: { data_dir: string; disk_total_bytes: number; disk_free_bytes: number };
  models: Record<string, { status: string; note: string }>;
  config: { sample_fps: number; max_concurrent_jobs: number; video_extensions: string[] };
}

export interface Stats {
  total_videos: number;
  by_status: Record<IndexingStatus, number>;
  duplicates: number;
  total_duration_seconds: number;
  total_size_bytes: number;
  total_detections: number;
  library_folders: number;
}

export interface Video {
  id: number;
  path: string;
  filename: string;
  size_bytes: number;
  duplicate_of_id: number | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  frame_rate: number | null;
  codec: string | null;
  indexing_status: IndexingStatus;
  indexing_progress: number;
  error_message: string | null;
  created_at: string;
}

export interface VideoPage { items: Video[]; total: number; limit: number; offset: number }

export interface LibraryFolder { id: number; path: string; last_scanned_at: string | null; video_count: number }

export interface IndexJob {
  id: number;
  job_type: "scan" | "index";
  status: JobStatus;
  params: Record<string, unknown>;
  progress: number;
  processed_frames: number;
  result: Record<string, number> | null;
  error_message: string | null;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the backend. Is it running on 127.0.0.1:8000?");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error;
    throw new ApiError(res.status, err?.code ?? "http_error", err?.message ?? res.statusText);
  }
  return body as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  systemInfo: () => request<SystemInfo>("/api/system-info"),
  stats: () => request<Stats>("/api/stats"),
  videos: (params: { q?: string; status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<VideoPage>(`/api/videos?${qs}`);
  },
  folders: () => request<LibraryFolder[]>("/api/library-folders"),
  scan: (path: string) =>
    request<IndexJob>("/api/videos/scan", { method: "POST", body: JSON.stringify({ path }) }),
  jobs: () => request<IndexJob[]>("/api/index-jobs"),
  cancelJob: (id: number) => request<IndexJob>(`/api/index-jobs/${id}/cancel`, { method: "POST" }),
};

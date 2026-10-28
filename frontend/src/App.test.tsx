import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

type Handler = (init?: RequestInit) => { status?: number; body: unknown };

let routes: Record<string, Handler>;
const calls: { url: string; init?: RequestInit }[] = [];

function json(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

const emptyStats = {
  total_videos: 2, duplicates: 0, total_duration_seconds: 125, total_size_bytes: 1000,
  total_detections: 0, library_folders: 1,
  by_status: { pending: 2, indexing: 0, indexed: 0, failed: 0, unsupported: 0, missing: 0 },
};

beforeEach(() => {
  calls.length = 0;
  routes = {
    "/api/stats": () => ({ body: emptyStats }),
    "/api/health": () => ({ body: { status: "ok", version: "0.2.0", database: "ok", schema_revision: "0001" } }),
    "/api/system-info": () => ({
      body: {
        hardware: {
          os: "Windows 11", python: "3.12.8", cpu: "Test CPU", cpu_logical_cores: 8, ram_total_mb: 16384,
          ram_available_mb: 8000, gpus: [], inference_provider: "cpu", inference_provider_reason: "no GPU",
          tools: [{ name: "ffmpeg", available: false, path: null, version: null }],
        },
        storage: { data_dir: "C:\\data", disk_total_bytes: 1e12, disk_free_bytes: 5e11 },
        models: { face: { status: "not_installed", note: "Added in Milestone 4" } },
        config: { sample_fps: 1, max_concurrent_jobs: 1, video_extensions: [".mp4"] },
      },
    }),
    "/api/library-folders": () => ({ body: [] }),
    "/api/videos": () => ({ body: { items: [], total: 0, limit: 50, offset: 0 } }),
    "/api/index-jobs": () => ({ body: [] }),
  };
  vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const key = Object.keys(routes)
      .sort((a, b) => b.length - a.length)
      .find((k) => url.split("?")[0] === k);
    if (!key) return json(404, { error: { code: "not_found", message: "Not found" } });
    const r = routes[key](init);
    return json(r.status ?? 200, r.body);
  });
});

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </MemoryRouter>,
  );
}

describe("Dashboard", () => {
  it("shows counts, CPU provider and missing FFmpeg warning", async () => {
    renderAt("/");
    expect(await screen.findByText("2:05")).toBeInTheDocument();
    expect(await screen.findByText(/— no GPU/)).toBeInTheDocument();
    expect(screen.getByText(/Not found on PATH/)).toBeInTheDocument();
    expect(screen.getByText(/never proof of identity/)).toBeInTheDocument();
  });

  it("shows an error when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", () => Promise.reject(new TypeError("Failed to fetch")));
    renderAt("/");
    expect((await screen.findAllByRole("alert"))[0]).toHaveTextContent(/Cannot reach the backend/);
  });
});

describe("Library", () => {
  it("shows empty state and submits a scan", async () => {
    routes["/api/videos/scan"] = () => ({ status: 202, body: { id: 7, status: "queued" } });
    renderAt("/library");
    expect(await screen.findByText(/No videos yet/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Folder path"), { target: { value: "D:\\CCTV" } });
    fireEvent.click(screen.getByRole("button", { name: "Scan recursively" }));

    expect(await screen.findByText(/Scan job #7 queued/)).toBeInTheDocument();
    const post = calls.find((c) => c.url === "/api/videos/scan");
    expect(post?.init?.method).toBe("POST");
    expect(JSON.parse(String(post?.init?.body))).toEqual({ path: "D:\\CCTV" });
  });

  it("shows the backend's validation message", async () => {
    routes["/api/videos/scan"] = () => ({
      status: 400,
      body: { error: { code: "invalid_path", message: "Folder does not exist" } },
    });
    renderAt("/library");
    fireEvent.change(screen.getByLabelText("Folder path"), { target: { value: "X:\\nope" } });
    fireEvent.click(screen.getByRole("button", { name: "Scan recursively" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Folder does not exist");
  });

  it("lists videos with metadata and errors", async () => {
    routes["/api/videos"] = () => ({
      body: {
        total: 1, limit: 50, offset: 0,
        items: [{
          id: 3, path: "D:\\CCTV\\cam 1\\yard.avi", filename: "yard.avi", size_bytes: 2048,
          duplicate_of_id: 1, duration_seconds: 61, width: 1280, height: 720, frame_rate: 25, codec: "h264",
          indexing_status: "failed", indexing_progress: 0, error_message: "Could not read video metadata",
          created_at: "2024-01-01T00:00:00Z",
        }],
      },
    });
    renderAt("/library");
    expect(await screen.findByText("yard.avi")).toBeInTheDocument();
    expect(screen.getByText("1280×720")).toBeInTheDocument();
    expect(screen.getByText("Duplicate of #1")).toBeInTheDocument();
    expect(screen.getByText("Could not read video metadata")).toBeInTheDocument();
  });
});

describe("Jobs", () => {
  it("cancels a running job", async () => {
    let cancelled = false;
    routes["/api/index-jobs"] = () => ({
      body: [{
        id: 4, job_type: "scan", status: cancelled ? "cancelled" : "running", params: { path: "D:\\CCTV" },
        progress: 0, processed_frames: 0, result: { discovered: 10, new: 8, changed: 0, unchanged: 2 },
        error_message: null, cancel_requested: cancelled, created_at: "", started_at: null, finished_at: null,
      }],
    });
    routes["/api/index-jobs/4/cancel"] = () => {
      cancelled = true;
      return { body: {} };
    };
    renderAt("/jobs");
    expect(await screen.findByText(/10 found · 8 new/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.getByText("cancelled")).toBeInTheDocument());
  });
});

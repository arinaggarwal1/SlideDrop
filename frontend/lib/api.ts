declare global {
  interface Window {
    __SLIDEDROP_API_BASE__?: string;
  }
}

function normalizeApiBase(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  return value.replace(/\/$/, "");
}

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const queryApiBase = normalizeApiBase(params.get("apiBase"));
    if (queryApiBase) {
      return queryApiBase;
    }

    const runtimeApiBase = normalizeApiBase(window.__SLIDEDROP_API_BASE__);
    if (runtimeApiBase) {
      return runtimeApiBase;
    }

    const { protocol, hostname, port } = window.location;
    if ((protocol === "http:" || protocol === "https:") && port && port !== "3000" && port !== "3001") {
      return `${protocol}//${hostname}:${port}`;
    }
  }

  return process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
}

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${normalizedPath}`;
}

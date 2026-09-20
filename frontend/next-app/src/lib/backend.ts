// Server-only helper: every call to the real Disha AI backend goes through here so the API key
// never reaches the browser. Route handlers under src/app/api/ are the only callers.

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000/v1";

export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const apiKey = process.env.BACKEND_API_KEY;
  if (!apiKey) {
    throw new Error("BACKEND_API_KEY is not set (see frontend/next-app/.env.local)");
  }
  return fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: {
      "X-API-Key": apiKey,
      "X-User-Id": "demo",
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });
}

export async function proxy(path: string, init?: RequestInit): Promise<Response> {
  try {
    const upstream = await backendFetch(path, init);
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Could not reach the backend";
    return Response.json({ error: { code: "UPSTREAM_UNAVAILABLE", message } }, { status: 502 });
  }
}

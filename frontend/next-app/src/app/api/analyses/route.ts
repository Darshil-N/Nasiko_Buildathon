import { proxy } from "@/lib/backend";

export async function POST(req: Request) {
  const body = await req.text();
  return proxy("/analyses", { method: "POST", body });
}

export async function GET() {
  return proxy("/analyses");
}

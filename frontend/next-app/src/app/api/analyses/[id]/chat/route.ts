import { proxy } from "@/lib/backend";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await req.text();
  return proxy(`/analyses/${id}/chat`, { method: "POST", body });
}

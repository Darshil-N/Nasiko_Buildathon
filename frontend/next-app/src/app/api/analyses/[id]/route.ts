import { proxy } from "@/lib/backend";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const format = new URL(req.url).searchParams.get("format");
  const suffix = format ? `?format=${format}` : "";
  return proxy(`/analyses/${id}${suffix}`);
}

import { NextResponse } from "next/server";
import { backend } from "@/lib/backend";
import { proxyError } from "@/lib/proxy";

export async function GET(_req: Request, { params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  try {
    const data = await backend.get(`/v1/jobs/${encodeURIComponent(jobId)}`);
    return NextResponse.json(data);
  } catch (error) {
    return proxyError(error);
  }
}

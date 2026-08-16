import { NextResponse } from "next/server";
import { backend } from "@/lib/backend";
import { proxyError } from "@/lib/proxy";
import type { TraceDetail } from "@/lib/types";

export async function GET(_req: Request, { params }: { params: Promise<{ traceId: string }> }) {
  const { traceId } = await params;
  try {
    const data = await backend.get<TraceDetail>(`/v1/traces/${encodeURIComponent(traceId)}`);
    return NextResponse.json(data);
  } catch (error) {
    return proxyError(error);
  }
}

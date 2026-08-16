import { NextRequest, NextResponse } from "next/server";
import { backend, BackendError } from "@/lib/backend";
import { proxyError } from "@/lib/proxy";
import type { Investigation, InvestigationPending } from "@/lib/types";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ traceId: string }> }) {
  const { traceId } = await params;
  try {
    const data = await backend.get<Investigation | InvestigationPending>(
      `/v1/investigations/${encodeURIComponent(traceId)}`,
    );
    return NextResponse.json(data);
  } catch (error) {
    // 202 (devam ediyor) ve 404 (henüz yok) UI için beklenen durumlar —
    // istisna olarak değil, normal gövde olarak iletilir.
    if (error instanceof BackendError && (error.status === 202 || error.status === 404)) {
      return NextResponse.json(error.body, { status: error.status });
    }
    return proxyError(error);
  }
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ traceId: string }> }) {
  const { traceId } = await params;
  const force = req.nextUrl.searchParams.get("force");
  const qs = force ? `?force=${force}` : "";
  try {
    const data = await backend.post(
      `/v1/anomalies/${encodeURIComponent(traceId)}/investigate${qs}`,
    );
    return NextResponse.json(data, { status: 202 });
  } catch (error) {
    return proxyError(error);
  }
}

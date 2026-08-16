import { NextResponse } from "next/server";
import { BackendError } from "@/lib/backend";

/** `BackendError`'ı olduğu gibi (aynı status + problem+json gövdesiyle)
 * istemciye ileten ortak hata dönüştürücü — Route Handler'larda tekrarı önler. */
export function proxyError(error: unknown): NextResponse {
  if (error instanceof BackendError) {
    return NextResponse.json(
      error.body ?? { title: "Backend error", status: error.status },
      { status: error.status },
    );
  }
  console.error("agentguard proxy error", error);
  return NextResponse.json(
    { title: "Upstream unreachable", status: 502, detail: "AgentGuard API'sine ulaşılamadı." },
    { status: 502 },
  );
}

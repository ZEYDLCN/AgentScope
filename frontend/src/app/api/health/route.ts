import { NextResponse } from "next/server";
import { backendBaseUrl } from "@/lib/backend";

export interface HealthResponse {
  status: "ok" | "not_ready" | "unreachable";
  checks?: Record<string, boolean>;
}

export async function GET() {
  try {
    const response = await fetch(`${backendBaseUrl()}/health/ready`, { cache: "no-store" });
    const body = (await response.json()) as HealthResponse;
    return NextResponse.json(body, { status: 200 });
  } catch {
    return NextResponse.json({ status: "unreachable" } satisfies HealthResponse, { status: 200 });
  }
}

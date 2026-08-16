import { NextResponse } from "next/server";
import { backend } from "@/lib/backend";
import { proxyError } from "@/lib/proxy";
import type { Stats } from "@/lib/types";

export async function GET() {
  try {
    const stats = await backend.get<Stats>("/v1/stats");
    return NextResponse.json(stats);
  } catch (error) {
    return proxyError(error);
  }
}

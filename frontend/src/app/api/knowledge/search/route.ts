import { NextRequest, NextResponse } from "next/server";
import { backend } from "@/lib/backend";
import { proxyError } from "@/lib/proxy";
import type { KnowledgeSearchResponse } from "@/lib/types";

export async function GET(req: NextRequest) {
  const qs = req.nextUrl.searchParams.toString();
  try {
    const data = await backend.get<KnowledgeSearchResponse>(`/v1/knowledge/search?${qs}`);
    return NextResponse.json(data);
  } catch (error) {
    return proxyError(error);
  }
}

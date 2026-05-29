import { NextResponse } from "next/server";
import { publicBackendFetch } from "@/lib/public-backend";
import type { PublicProfileQuestionAnswer } from "@/lib/types";

const corsHeaders = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "POST, OPTIONS",
  "access-control-allow-headers": "content-type"
};

export function OPTIONS() {
  return new Response(null, { status: 204, headers: corsHeaders });
}

export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  try {
    const body = await request.json();
    const question = typeof body?.question === "string" ? body.question : "";
    const answer = await publicBackendFetch<PublicProfileQuestionAnswer>(`/public/profiles/${slug}/ask`, {
      method: "POST",
      body: JSON.stringify({ question })
    });
    return NextResponse.json(answer, { headers: corsHeaders });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to answer profile question";
    return NextResponse.json({ message }, { status: 500, headers: corsHeaders });
  }
}

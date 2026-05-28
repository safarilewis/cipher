import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import type { Evaluation } from "@/lib/types";

export async function GET() {
  try {
    const evaluation = await backendFetch<Evaluation | null>("/analysis/latest");
    return NextResponse.json(evaluation);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load analysis status";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

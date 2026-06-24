import { NextRequest, NextResponse } from "next/server";

export const maxDuration = 60; // Vercel Pro max function duration (seconds)

export async function POST(req: NextRequest) {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    return NextResponse.json(
      { error: "BACKEND_URL environment variable is not configured" },
      { status: 503 }
    );
  }

  try {
    const formData = await req.formData();
    const res = await fetch(`${backendUrl}/api/evaluate`, {
      method: "POST",
      body: formData,
      // No Content-Type header — let fetch set multipart boundary automatically
    });

    const body = await res.json();
    return NextResponse.json(body, { status: res.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: `Backend request failed: ${message}` }, { status: 502 });
  }
}

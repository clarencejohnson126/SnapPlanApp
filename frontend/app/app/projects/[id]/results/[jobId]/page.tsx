import { redirect } from "next/navigation";

interface PageProps {
  params: Promise<{ id: string; jobId: string }>;
}

export default async function ResultsPage({ params }: PageProps) {
  // In MVP mode without auth, redirect to Quick Scan
  redirect("/app/scan");
}

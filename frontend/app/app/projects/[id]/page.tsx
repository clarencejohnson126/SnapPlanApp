import Link from "next/link";
import { redirect } from "next/navigation";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ProjectDetailPage({ params }: PageProps) {
  // In MVP mode without auth, redirect to Quick Scan
  redirect("/app/scan");
}

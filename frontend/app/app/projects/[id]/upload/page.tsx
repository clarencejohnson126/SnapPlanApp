import { redirect } from "next/navigation";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function UploadPage({ params }: PageProps) {
  // In MVP mode without auth, redirect to Quick Scan
  redirect("/app/scan");
}

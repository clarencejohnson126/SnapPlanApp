import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { Sidebar, Topbar } from "@/components/app";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/auth/login");
  }

  return (
    <div className="min-h-screen bg-[#0F1B2A]">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="ml-60 min-h-screen flex flex-col">
        {/* Topbar */}
        <Topbar userEmail={user.email} />

        {/* Page Content */}
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}

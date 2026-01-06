import { Sidebar, Topbar } from "@/components/app";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#0F1B2A]">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="ml-60 min-h-screen flex flex-col">
        {/* Topbar */}
        <Topbar userEmail="guest@snapplan.app" />

        {/* Page Content */}
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}

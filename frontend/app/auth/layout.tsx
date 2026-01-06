/**
 * Auth Layout
 *
 * Simple centered layout for authentication pages.
 * No sidebar, topbar, or other app chrome.
 */

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#0F1B2A] flex items-center justify-center p-4">
      {/* Blueprint background pattern (subtle) */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0, 212, 170, 0.3) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 212, 170, 0.3) 1px, transparent 1px)
          `,
          backgroundSize: "50px 50px",
        }}
      />

      {/* Content */}
      <div className="relative z-10 w-full max-w-md">{children}</div>
    </div>
  );
}

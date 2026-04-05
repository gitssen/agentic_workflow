import Chat from "@/components/Chat";
import MusicWidget from "@/components/MusicWidget";

export default function Home() {
  return (
    <main className="relative flex h-screen w-full overflow-hidden bg-background">
      {/* Background Mesh */}
      <div className="mesh-bg">
        <div className="mesh-blob mesh-blob-1" />
        <div className="mesh-blob mesh-blob-2" />
        <div className="mesh-blob mesh-blob-3" />
      </div>

      {/* Sidebar */}
      <aside className="hidden lg:flex w-80 flex-col z-10 shrink-0">
        <MusicWidget />
      </aside>

      {/* Main Content */}
      <section className="flex-1 flex flex-col relative z-10 overflow-hidden">
        <Chat />
      </section>
    </main>
  );
}

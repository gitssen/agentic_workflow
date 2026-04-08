"use client";

import { useState, useEffect } from "react";
import { Sparkles, ChevronDown, Terminal, MessageSquare, Compass, Zap } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import Chat from "@/components/Chat";
import Curator from "@/components/Curator";

export default function Home() {
  const [activeView, setActiveView] = useState<"agents" | "music">("agents");
  const [personas, setPersonas] = useState<string[]>(["general"]);
  const [selectedPersona, setSelectedPersona] = useState("general");

  useEffect(() => {
    fetch("http://192.168.1.100:8000/personas")
      .then((res) => res.json())
      .then((data) => {
        if (data && Array.isArray(data.personas)) {
          setPersonas(data.personas);
        } else if (Array.isArray(data)) {
          setPersonas(data);
        }
      })
      .catch((err) => console.error("Failed to fetch personas", err));
  }, []);

  return (
    <main className="relative flex h-screen w-full overflow-hidden bg-zinc-950 text-white selection:bg-indigo-500/30 font-sans">
      {/* Mesh Background */}
      <div className="fixed inset-0 overflow-hidden z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[60%] h-[60%] bg-indigo-900/20 blur-[120px] rounded-full animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-900/20 blur-[120px] rounded-full animate-pulse" style={{ animationDelay: "2s" }} />
      </div>

      <div className="flex-1 flex flex-col relative z-10 overflow-hidden">
        {/* Unified Header */}
        <header className="flex items-center justify-between px-12 h-24 border-b border-white/5 bg-zinc-950/50 backdrop-blur-3xl shrink-0">
          <div className="flex items-center gap-12">
            <div className="flex items-center gap-5">
              <div className="relative">
                <div className="absolute inset-0 bg-indigo-500/30 blur-2xl rounded-full animate-pulse" />
                <div className="relative p-3 bg-indigo-600 rounded-2xl shadow-2xl border border-white/10">
                  <Zap className="text-white w-6 h-6" />
                </div>
              </div>
              <div className="hidden sm:block">
                <h1 className="font-black text-xl tracking-tighter text-white leading-none">AGENTIC</h1>
                <p className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.3em] mt-1">Matrix OS v2.5</p>
              </div>
            </div>

            {/* View Switcher */}
            <nav className="flex p-1.5 glass rounded-2xl border border-white/5 bg-white/5 backdrop-blur-3xl">
              <button 
                onClick={() => setActiveView("agents")}
                className={cn(
                  "flex items-center gap-3 px-6 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all",
                  activeView === "agents" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20" : "text-zinc-500 hover:text-zinc-200"
                )}
              >
                <MessageSquare size={16} />
                Agents
              </button>
              <button 
                onClick={() => setActiveView("music")}
                className={cn(
                  "flex items-center gap-3 px-6 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all",
                  activeView === "music" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20" : "text-zinc-500 hover:text-zinc-200"
                )}
              >
                <Compass size={16} />
                Music
              </button>
            </nav>
          </div>

          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <div className="hidden md:flex flex-col items-end">
                <p className="text-[10px] font-black text-zinc-600 uppercase tracking-tighter">System Persona</p>
                <p className="text-sm font-black text-indigo-400 tracking-tighter uppercase">{selectedPersona.replace("_", " ")}</p>
              </div>
              <div className="relative group">
                <select
                  value={selectedPersona}
                  onChange={(e) => setSelectedPersona(e.target.value)}
                  className="appearance-none bg-white/5 text-zinc-200 py-3 pl-6 pr-12 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] border border-white/5 focus:ring-2 focus:ring-indigo-500/50 transition-all cursor-pointer hover:bg-white/10"
                >
                  {personas.map((p) => (
                    <option key={p} value={p} className="bg-zinc-900 text-white">
                      {p.replace("_", " ")}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 pointer-events-none group-hover:text-indigo-400 transition-colors" />
              </div>
            </div>
            
            <div className="h-10 w-px bg-white/5 mx-2" />
            
            <div className="flex items-center gap-3">
               <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
               <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest hidden lg:block">Core Connected</p>
            </div>
          </div>
        </header>

        {/* Dynamic Content Area */}
        <div className="flex-1 relative overflow-hidden">
          <AnimatePresence mode="wait">
            {activeView === "agents" ? (
              <motion.div 
                key="agents"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 1.02 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="absolute inset-0"
              >
                <Chat selectedPersona={selectedPersona} />
              </motion.div>
            ) : (
              <motion.div 
                key="music"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 1.02 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="absolute inset-0"
              >
                <Curator />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </main>
  );
}

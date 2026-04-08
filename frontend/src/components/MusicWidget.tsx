"use client";

import { useEffect, useState } from "react";
import { Music, Database, Radio, Play, Pause, SkipForward, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import Link from "next/link";

export default function MusicWidget() {
  const [songCount, setSongCount] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // Simplified polling for song count
  useEffect(() => {
    const fetchCount = async () => {
      try {
        // In a real app, we'd have a specific /stats endpoint
        // For now, we'll just simulate or use a placeholder
        setSongCount(142); // Placeholder
      } catch (e) {
        console.error(e);
      }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col gap-6 p-6 h-full glass rounded-none border-y-0 border-l-0">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-xs font-black uppercase tracking-[0.2em] text-indigo-500/80">System Status</h2>
          <p className="text-sm font-medium text-slate-500 dark:text-zinc-400">Environment: Production</p>
        </div>
        <Link 
          href="/music" 
          className="p-2 bg-indigo-500/10 text-indigo-500 rounded-lg hover:bg-indigo-500 hover:text-white transition-all group"
          title="Open Music App"
        >
          <ExternalLink size={18} className="group-hover:scale-110 transition-transform" />
        </Link>
      </div>

      {/* Stats Card */}
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="p-4 bg-indigo-500/5 dark:bg-indigo-500/10 rounded-2xl border border-indigo-500/10 flex items-center gap-4"
      >
        <div className="p-3 bg-indigo-500 rounded-xl text-white shadow-lg shadow-indigo-500/20">
          <Database size={20} />
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-indigo-500/60">Indexed Songs</p>
          <p className="text-xl font-black text-slate-800 dark:text-zinc-100">{songCount || "..."}</p>
        </div>
      </motion.div>

      {/* Now Playing (Simulation) */}
      <div className="flex-1 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-black uppercase tracking-[0.2em] text-indigo-500/80">Now Playing</h2>
          <Radio size={14} className="text-red-500 animate-pulse" />
        </div>
        
        <div className="aspect-square rounded-3xl bg-gradient-to-br from-slate-200 to-slate-300 dark:from-zinc-800 dark:to-zinc-900 border border-white/10 flex items-center justify-center relative overflow-hidden group shadow-inner">
           <Music className="w-20 h-20 text-slate-400 dark:text-zinc-700" />
           <div className="absolute inset-0 bg-indigo-500/20 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>

        <div className="space-y-1">
          <p className="font-bold text-slate-800 dark:text-zinc-100 truncate">Hymn for the Weekend</p>
          <p className="text-xs font-medium text-slate-500 dark:text-zinc-400">Coldplay • A Head Full of Dreams</p>
        </div>

        {/* Mini Controls */}
        <div className="flex items-center justify-center gap-6 pt-2">
          <button className="text-slate-400 hover:text-indigo-500 transition-colors">
            <SkipForward size={20} className="rotate-180" />
          </button>
          <button 
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-4 bg-slate-800 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-full hover:scale-105 active:scale-95 transition-all shadow-xl"
          >
            {isPlaying ? <Pause size={24} fill="currentColor" /> : <Play size={24} fill="currentColor" />}
          </button>
          <button className="text-slate-400 hover:text-indigo-500 transition-colors">
            <SkipForward size={20} />
          </button>
        </div>

        {/* Fake Progress Bar */}
        <div className="space-y-2 pt-4">
          <div className="h-1 w-full bg-slate-200 dark:bg-zinc-800 rounded-full overflow-hidden">
            <motion.div 
              initial={{ width: "0%" }}
              animate={{ width: isPlaying ? "45%" : "45%" }}
              className="h-full bg-indigo-500"
            />
          </div>
          <div className="flex justify-between text-[10px] font-bold text-slate-400 uppercase">
            <span>1:42</span>
            <span>3:50</span>
          </div>
        </div>
      </div>

      <div className="p-4 rounded-2xl border border-dashed border-slate-200 dark:border-zinc-800 flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">MCP Server Online</span>
      </div>
    </div>
  );
}

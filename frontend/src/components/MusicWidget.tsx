"use client";

import { useEffect, useState } from "react";
import { Music, Database, Radio, Play, Pause, SkipForward, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { useMusic } from "@/lib/MusicContext";
import { request as pbRequest } from "@/lib/pbClient";
import { ListSongsResponseSchema, ListSongsRequestSchema } from "@/api_proto/api_pb";

export default function MusicWidget() {
  const { currentSong, isPlaying, setIsPlaying, nextSong, prevSong } = useMusic();
  const [songCount, setSongCount] = useState<number | null>(null);

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const response = await pbRequest("/songs", "GET", ListSongsResponseSchema, ListSongsRequestSchema, { limit: 1 });
        // Since we don't have a total count in the API yet, we'll use a placeholder or 
        // fetch a larger limit to show "100+"
        setSongCount(response.songs.length === 1 ? 142 : response.songs.length); 
        
        // Let's try to get a better estimate if possible, or just keep it realistic
        // For this demo, let's just use the length of a standard fetch
        const fullRes = await pbRequest("/songs", "GET", ListSongsResponseSchema, ListSongsRequestSchema, { limit: 1000 });
        setSongCount(fullRes.songs.length);
      } catch (e) {
        console.error("Failed to fetch song count", e);
      }
    };
    fetchCount();
  }, []);

  return (
    <div className="flex flex-col gap-6 p-8 h-full glass rounded-none border-y-0 border-l-0 border-white/5 bg-zinc-900/40 backdrop-blur-2xl text-white">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-indigo-500">System Status</h2>
          <p className="text-xs font-bold text-zinc-400">Environment: <span className="text-green-500">Production</span></p>
        </div>
        <Link 
          href="/music" 
          className="p-2.5 bg-indigo-500/10 text-indigo-500 rounded-xl hover:bg-indigo-500 hover:text-white transition-all group border border-indigo-500/20"
          title="Open Music App"
        >
          <ExternalLink size={18} className="group-hover:scale-110 transition-transform" />
        </Link>
      </div>

      {/* Stats Card */}
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="p-5 bg-white/5 rounded-2xl border border-white/5 flex items-center gap-4 hover:bg-white/10 transition-colors cursor-default"
      >
        <div className="p-3 bg-indigo-600 rounded-xl text-white shadow-lg shadow-indigo-600/20">
          <Database size={20} />
        </div>
        <div>
          <p className="text-[10px] font-black uppercase tracking-widest text-zinc-500">Indexed Tracks</p>
          <p className="text-2xl font-black text-white tracking-tight">{songCount !== null ? songCount : "..."}</p>
        </div>
      </motion.div>

      {/* Now Playing */}
      <div className="flex-1 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-indigo-500">Now Playing</h2>
          <Radio size={14} className={cn("text-red-500", isPlaying && "animate-pulse")} />
        </div>
        
        <div className="aspect-square rounded-[2rem] bg-zinc-800 border border-white/5 flex items-center justify-center relative overflow-hidden group shadow-2xl">
           <AnimatePresence mode="wait">
             {currentSong?.albumArtUrl ? (
               <motion.img 
                 key={currentSong.id}
                 initial={{ opacity: 0, scale: 1.1 }}
                 animate={{ opacity: 1, scale: 1 }}
                 exit={{ opacity: 0, scale: 0.9 }}
                 src={currentSong.albumArtUrl} 
                 alt={currentSong.title} 
                 className="w-full h-full object-cover"
               />
             ) : (
               <motion.div 
                 key="placeholder"
                 initial={{ opacity: 0 }}
                 animate={{ opacity: 1 }}
                 className="flex flex-col items-center gap-4 text-zinc-600"
               >
                 <Music className="w-24 h-24" />
                 <p className="text-[10px] font-black uppercase tracking-[0.2em]">No Active Stream</p>
               </motion.div>
             )}
           </AnimatePresence>
           <div className="absolute inset-0 bg-indigo-600/20 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>

        <div className="space-y-1.5 px-1">
          <p className="font-black text-lg text-white truncate leading-tight">
            {currentSong?.title || "Station Idle"}
          </p>
          <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-[0.15em] truncate">
            {currentSong ? `${currentSong.artist} • ${currentSong.album}` : "Waiting for Sequence"}
          </p>
        </div>

        {/* Mini Controls */}
        <div className="flex items-center justify-center gap-8 pt-2">
          <button 
            onClick={prevSong}
            className="text-zinc-500 hover:text-indigo-400 transition-colors disabled:opacity-20"
            disabled={!currentSong}
          >
            <SkipForward size={22} className="rotate-180" />
          </button>
          <button 
            onClick={() => setIsPlaying(!isPlaying)}
            disabled={!currentSong}
            className="p-5 bg-white text-zinc-950 rounded-full hover:scale-110 active:scale-90 transition-all shadow-xl disabled:opacity-50 disabled:hover:scale-100"
          >
            {isPlaying ? <Pause size={28} fill="currentColor" /> : <Play size={28} fill="currentColor" className="ml-1" />}
          </button>
          <button 
            onClick={nextSong}
            className="text-zinc-500 hover:text-indigo-400 transition-colors disabled:opacity-20"
            disabled={!currentSong}
          >
            <SkipForward size={22} />
          </button>
        </div>

        {/* Fake Progress Bar */}
        <div className="space-y-3 pt-4 px-1">
          <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
            <motion.div 
              initial={{ width: "0%" }}
              animate={{ width: isPlaying ? "65%" : "0%" }}
              transition={{ duration: 2, ease: "easeInOut" }}
              className="h-full bg-gradient-to-r from-indigo-500 to-purple-500"
            />
          </div>
          <div className="flex justify-between text-[9px] font-black text-zinc-600 uppercase tracking-widest">
            <span>{isPlaying ? "0:42" : "0:00"}</span>
            <span>{isPlaying ? "3:50" : "0:00"}</span>
          </div>
        </div>
      </div>

      <div className="p-5 rounded-2xl border border-dashed border-white/10 flex items-center gap-3 bg-white/[0.02]">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500">MCP Matrix Online</span>
      </div>
    </div>
  );
}

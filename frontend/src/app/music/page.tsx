"use client";

import { useState, useEffect } from "react";
import { Search, Sparkles, Music, Play, Pause, ListMusic, Loader2, Save, X, History, Clock, LayoutGrid, List } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import MusicPlayer from "@/components/MusicPlayer";
import { cn } from "@/lib/utils";

interface Song {
  id: string;
  title: string;
  artist: string;
  album: string;
  album_art_url?: string;
}

interface SavedPlaylist {
  id: string;
  name: string;
  prompt: string;
  songs: Song[];
  created_at: string | number | Date | null;
}

export default function CuratorPage() {
  const [prompt, setPrompt] = useState("");
  const [playlist, setPlaylist] = useState<Song[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentSongIndex, setCurrentSongIndex] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  
  // Saving functionality
  const [isSaveModalOpen, setIsSaveModalOpen] = useState(false);
  const [playlistName, setPlaylistName] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [savedPlaylists, setSavedPlaylists] = useState<SavedPlaylist[]>([]);

  useEffect(() => {
    fetchSavedPlaylists();
  }, []);

  const fetchSavedPlaylists = async () => {
    try {
      const res = await fetch("http://localhost:8000/playlists");
      if (res.ok) {
        const data = await res.json();
        setSavedPlaylists(data);
      }
    } catch (e) {
      console.error("Failed to fetch playlists", e);
    }
  };

  const handleCurate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isLoading) return;

    setIsLoading(true);
    setPlaylist([]);
    setCurrentSongIndex(null);

    try {
      const response = await fetch("http://localhost:8000/curate_playlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      if (!response.ok) throw new Error("Curation failed");
      const data = await response.json();
      setPlaylist(data.playlist);
    } catch (error) {
      console.error("Curation error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSavePlaylist = async () => {
    if (!playlistName.trim() || playlist.length === 0) return;
    setIsSaving(true);
    try {
      const response = await fetch("http://localhost:8000/playlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: playlistName,
          prompt: prompt,
          songs: playlist
        }),
      });
      if (response.ok) {
        setIsSaveModalOpen(false);
        setPlaylistName("");
        fetchSavedPlaylists();
      }
    } catch (e) {
      console.error("Failed to save", e);
    } finally {
      setIsSaving(false);
    }
  };

  const loadPlaylist = (p: SavedPlaylist) => {
    setPlaylist(p.songs);
    setPrompt(p.prompt);
    setCurrentSongIndex(null);
  };

  const handlePlaySong = (index: number) => {
    setCurrentSongIndex(index);
  };

  const handleNext = () => {
    if (currentSongIndex !== null && currentSongIndex < playlist.length - 1) {
      setCurrentSongIndex(currentSongIndex + 1);
    }
  };

  const handlePrev = () => {
    if (currentSongIndex !== null && currentSongIndex > 0) {
      setCurrentSongIndex(currentSongIndex - 1);
    }
  };

  return (
    <div className="flex h-screen bg-zinc-950 text-white selection:bg-indigo-500/30 font-sans overflow-hidden">
      {/* Mesh Background */}
      <div className="fixed inset-0 overflow-hidden z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[60%] h-[60%] bg-indigo-900/20 blur-[120px] rounded-full animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-900/20 blur-[120px] rounded-full animate-pulse" style={{ animationDelay: "2s" }} />
      </div>

      {/* Sidebar: Saved Playlists */}
      <aside className="w-80 glass border-r border-white/5 flex flex-col z-20 relative">
        <div className="p-8 border-b border-white/5">
           <h2 className="text-xs font-black uppercase tracking-[0.3em] text-indigo-500 flex items-center gap-2">
              <History size={14} />
              Saved Sequences
           </h2>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
           {savedPlaylists.map((p) => (
             <button
               key={p.id}
               onClick={() => loadPlaylist(p)}
               className="w-full text-left p-4 rounded-2xl hover:bg-white/5 transition-all group border border-transparent hover:border-white/5"
             >
               <p className="font-black text-sm truncate group-hover:text-indigo-400 transition-colors">{p.name}</p>
               <div className="flex items-center gap-2 mt-1 opacity-40">
                  <Clock size={10} />
                  <span className="text-[10px] font-bold uppercase tracking-widest">{p.songs.length} Tracks</span>
               </div>
             </button>
           ))}
           {savedPlaylists.length === 0 && (
             <div className="py-10 text-center opacity-20">
                <Music size={32} className="mx-auto mb-2" />
                <p className="text-[10px] font-black uppercase tracking-widest">No Saved Playlists</p>
             </div>
           )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 relative z-10 overflow-y-auto custom-scrollbar pb-32">
        <div className="max-w-5xl mx-auto px-8 pt-16">
            {/* Header */}
            <header className="text-center space-y-4 mb-12">
            <motion.div 
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-black uppercase tracking-[0.2em]"
            >
                <Sparkles size={14} />
                AI Music Concierge
            </motion.div>
            <motion.h1 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-6xl font-black tracking-tighter"
            >
                Vibe <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500">Curator</span>
            </motion.h1>
            </header>

            {/* Search Area */}
            <div className="max-w-2xl mx-auto mb-16">
            <form onSubmit={handleCurate} className="relative group">
                <div className="absolute inset-0 bg-indigo-500/10 blur-2xl group-focus-within:bg-indigo-500/20 transition-all rounded-[3rem]" />
                <div className="relative glass p-2 rounded-[3rem] flex items-center gap-2 border-white/10 group-focus-within:border-indigo-500/50 transition-all">
                <div className="pl-6 text-zinc-500 group-focus-within:text-indigo-500 transition-colors">
                    <Search size={24} />
                </div>
                <input 
                    type="text"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Describe a vibe..."
                    className="flex-1 bg-transparent py-4 px-4 text-lg font-bold placeholder-zinc-700 focus:outline-none tracking-tight"
                />
                <button 
                    type="submit"
                    disabled={isLoading || !prompt.trim()}
                    className="p-4 bg-indigo-600 rounded-[2.5rem] hover:bg-indigo-500 disabled:opacity-50 transition-all shadow-xl shadow-indigo-500/20 active:scale-95 flex items-center gap-3 font-black uppercase tracking-widest text-[10px]"
                >
                    {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
                    {isLoading ? "Curating..." : "Curate"}
                </button>
                </div>
            </form>
            </div>

            {/* Playlist View Controls */}
            <AnimatePresence mode="wait">
            {playlist.length > 0 ? (
                <motion.div 
                key="playlist"
                initial={{ opacity: 0, y: 40 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -40 }}
                className="space-y-8"
                >
                <div className="flex items-center justify-between border-b border-white/5 pb-6">
                    <h2 className="text-xl font-black flex items-center gap-3 tracking-tight">
                        <ListMusic className="text-indigo-500" />
                        Sequence Identified
                    </h2>
                    
                    <div className="flex items-center gap-4">
                        <div className="flex bg-white/5 p-1 rounded-xl border border-white/5">
                            <button 
                                onClick={() => setViewMode("grid")}
                                className={cn(
                                    "p-2 rounded-lg transition-all",
                                    viewMode === "grid" ? "bg-indigo-600 text-white shadow-lg" : "text-zinc-500 hover:text-zinc-300"
                                )}
                            >
                                <LayoutGrid size={16} />
                            </button>
                            <button 
                                onClick={() => setViewMode("list")}
                                className={cn(
                                    "p-2 rounded-lg transition-all",
                                    viewMode === "list" ? "bg-indigo-600 text-white shadow-lg" : "text-zinc-500 hover:text-zinc-300"
                                )}
                            >
                                <List size={16} />
                            </button>
                        </div>

                        <button 
                            onClick={() => setIsSaveModalOpen(true)}
                            className="flex items-center gap-2 px-4 py-2.5 bg-white/5 hover:bg-white/10 rounded-xl transition-all text-[10px] font-black uppercase tracking-widest border border-white/5"
                        >
                            <Save size={14} />
                            Save Sequence
                        </button>
                    </div>
                </div>

                {viewMode === "grid" ? (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                        {playlist.map((song, index) => (
                        <motion.div 
                            key={song.id}
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: index * 0.05 }}
                            className="group cursor-pointer"
                            onClick={() => handlePlaySong(index)}
                        >
                            <div className="relative aspect-square rounded-3xl overflow-hidden mb-4 shadow-2xl border border-white/5 ring-0 ring-indigo-500/50 group-hover:ring-4 transition-all duration-500">
                            {song.album_art_url ? (
                                <img src={song.album_art_url} alt={song.title} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                            ) : (
                                <div className="w-full h-full bg-zinc-900 flex items-center justify-center text-zinc-800">
                                <Music size={48} />
                                </div>
                            )}
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                <div className={cn(
                                    "w-14 h-14 bg-white text-zinc-950 rounded-full flex items-center justify-center shadow-2xl transition-all duration-500 scale-75 group-hover:scale-100",
                                    currentSongIndex === index && "bg-indigo-500 text-white scale-100"
                                )}>
                                    {currentSongIndex === index ? <Pause size={28} fill="currentColor" /> : <Play size={28} fill="currentColor" className="ml-1" />}
                                </div>
                            </div>
                            </div>
                            <div className="space-y-0.5">
                            <h3 className={cn(
                                "font-black text-base tracking-tight truncate transition-colors",
                                currentSongIndex === index ? "text-indigo-500" : "text-white"
                            )}>{song.title || song.id.replace(/_/g, " ")}</h3>
                            <p className="text-[10px] font-bold text-zinc-500 truncate uppercase tracking-wider">{song.artist || "Unknown Artist"}</p>
                            </div>
                        </motion.div>
                        ))}
                    </div>
                ) : (
                    <div className="space-y-2">
                        {playlist.map((song, index) => (
                            <motion.div
                                key={song.id}
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: index * 0.03 }}
                                onClick={() => handlePlaySong(index)}
                                className={cn(
                                    "flex items-center gap-4 p-3 rounded-2xl cursor-pointer transition-all border border-transparent group hover:bg-white/5",
                                    currentSongIndex === index ? "bg-indigo-500/10 border-indigo-500/20" : ""
                                )}
                            >
                                <div className="w-12 h-12 rounded-xl overflow-hidden relative shrink-0">
                                    {song.album_art_url ? (
                                        <img src={song.album_art_url} alt={song.title} className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full bg-zinc-900 flex items-center justify-center text-zinc-800">
                                            <Music size={20} />
                                        </div>
                                    )}
                                    <div className={cn(
                                        "absolute inset-0 bg-black/40 flex items-center justify-center transition-opacity",
                                        currentSongIndex === index ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                                    )}>
                                        {currentSongIndex === index ? <Pause size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" className="ml-0.5" />}
                                    </div>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <h3 className={cn(
                                        "font-black text-sm tracking-tight truncate",
                                        currentSongIndex === index ? "text-indigo-400" : "text-zinc-100"
                                    )}>{song.title || song.id.replace(/_/g, " ")}</h3>
                                    <p className="text-[10px] font-bold text-zinc-500 truncate uppercase tracking-widest">{song.artist || "Unknown Artist"} • {song.album || "Unknown Album"}</p>
                                </div>
                                <div className="px-4 text-[10px] font-black text-zinc-600 uppercase tracking-widest hidden md:block">
                                    {song.id.endsWith("_mp3") ? "MPEG" : "FLAC"}
                                </div>
                            </motion.div>
                        ))}
                    </div>
                )}
                </motion.div>
            ) : !isLoading && (
                <div className="text-center py-20 opacity-10">
                <Music size={80} className="mx-auto mb-4" />
                <p className="font-black uppercase tracking-[0.4em] text-[10px]">Awaiting Sequence</p>
                </div>
            )}
            </AnimatePresence>
        </div>
      </main>

      {/* Save Modal */}
      <AnimatePresence>
        {isSaveModalOpen && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsSaveModalOpen(false)}
              className="absolute inset-0 bg-zinc-950/80 backdrop-blur-sm"
            />
            <motion.div 
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="relative w-full max-w-md glass p-8 rounded-[2.5rem] border-white/10 shadow-2xl"
            >
              <button 
                onClick={() => setIsSaveModalOpen(false)}
                className="absolute top-6 right-6 text-zinc-500 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
              <h2 className="text-2xl font-black mb-2 tracking-tight">Save Sequence</h2>
              <p className="text-zinc-500 text-sm font-medium mb-6 tracking-tight">Give your curated collection a name to access it later.</p>
              
              <div className="space-y-4">
                <input 
                  autoFocus
                  type="text"
                  value={playlistName}
                  onChange={(e) => setPlaylistName(e.target.value)}
                  placeholder="e.g., Late Night Jazz, High Energy Focus..."
                  className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 px-6 font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all placeholder-zinc-700"
                />
                <button 
                  onClick={handleSavePlaylist}
                  disabled={isSaving || !playlistName.trim()}
                  className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-2xl font-black uppercase tracking-widest text-xs transition-all shadow-xl shadow-indigo-500/20 flex items-center justify-center gap-2"
                >
                  {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                  {isSaving ? "Saving..." : "Confirm Save"}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Global Player */}
      <MusicPlayer 
        currentSong={currentSongIndex !== null ? playlist[currentSongIndex] : null} 
        playlist={playlist}
        onNext={handleNext}
        onPrev={handlePrev}
      />
    </div>
  );
}

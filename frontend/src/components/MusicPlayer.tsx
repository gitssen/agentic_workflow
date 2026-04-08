"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Play, Pause, SkipBack, SkipForward, Volume2, Music, Cast, Loader2, Speaker } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useMusic } from "@/lib/MusicContext";

interface SonosDevice {
  name: string;
  ip: string;
}

export default function MusicPlayer() {
  const { currentSong, isPlaying, setIsPlaying, nextSong, prevSong } = useMusic();
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Sonos state
  const [isCastMenuOpen, setIsCastMenuOpen] = useState(false);
  const [devices, setDevices] = useState<SonosDevice[]>([]);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [activeCastIP, setActiveCastIP] = useState<string | null>(null);
  const [volume, setVolume] = useState(66);

  const formatTime = (time: number) => {
    if (isNaN(time)) return "0:00";
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const discoverDevices = async () => {
    setIsDiscovering(true);
    try {
      const res = await fetch("http://192.168.1.100:8000/sonos/devices");
      if (res.ok) {
        const data = await res.json();
        setDevices(data);
      }
    } catch (e) {
      console.error("Sonos discovery failed", e);
    } finally {
      setIsDiscovering(false);
    }
  };

  const castToDevice = async (device: SonosDevice) => {
    if (!currentSong) return;
    setActiveCastIP(device.ip);
    setIsPlaying(true); 
    if (audioRef.current) audioRef.current.pause();

    try {
      await fetch("http://192.168.1.100:8000/sonos/play", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip: device.ip, song_id: currentSong.id }),
      });
      setIsCastMenuOpen(false);
    } catch (e) {
      console.error("Cast failed", e);
      setActiveCastIP(null);
      setIsPlaying(false);
    }
  };

  const controlSonos = async (action: string, value?: number) => {
    if (!activeCastIP) return;
    try {
      await fetch("http://192.168.1.100:8000/sonos/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip: activeCastIP, action, value }),
      });
    } catch (e) {
      console.error(`Sonos control failed: ${action}`, e);
    }
  };

  const stopCasting = async () => {
    if (activeCastIP) {
        await controlSonos("stop");
        setActiveCastIP(null);
        setIsPlaying(false);
    }
    setIsCastMenuOpen(false);
  };

  useEffect(() => {
    if (currentSong && audioRef.current) {
      const streamUrl = `http://192.168.1.100:8000/stream/${currentSong.id}`;
      if (audioRef.current.src !== streamUrl) {
          audioRef.current.src = streamUrl;
      }
      
      // If we are currently casting, update the cast device instead of local play
      if (activeCastIP) {
        fetch("http://192.168.1.100:8000/sonos/play", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ip: activeCastIP, song_id: currentSong.id }),
        });
      } else if (isPlaying) {
        audioRef.current.play().catch(console.error);
      }
    }
  }, [currentSong, isPlaying, activeCastIP]);

  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  }, []);

  const handleLoadedMetadata = useCallback(() => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    audio.addEventListener("timeupdate", handleTimeUpdate);
    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    audio.addEventListener("ended", nextSong);

    return () => {
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("ended", nextSong);
    };
  }, [handleTimeUpdate, handleLoadedMetadata, nextSong]);

  const togglePlay = () => {
    if (activeCastIP) {
        const nextState = !isPlaying;
        setIsPlaying(nextState);
        controlSonos(nextState ? "resume" : "pause");
        return;
    }

    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch(console.error);
    }
    setIsPlaying(!isPlaying);
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (activeCastIP && isPlaying) {
        interval = setInterval(async () => {
            try {
                const res = await fetch(`http://192.168.1.100:8000/sonos/status/${activeCastIP}`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.position !== undefined) setCurrentTime(data.position);
                    if (data.duration) setDuration(data.duration);
                }
            } catch (e) {
                console.error("Failed to poll Sonos status", e);
            }
        }, 2000);
    }
    return () => clearInterval(interval);
  }, [activeCastIP, isPlaying]);

  const handleProgressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    if (activeCastIP) {
        setCurrentTime(newTime);
        controlSonos("seek", newTime);
        return;
    }
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
    setCurrentTime(newTime);
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value);
    setVolume(val);
    if (activeCastIP) {
        controlSonos("volume", val);
    } else if (audioRef.current) {
        audioRef.current.volume = val / 100;
    }
  };

  if (!currentSong) return null;

  const artUrl = currentSong.albumArtUrl || currentSong.album_art_url;

  return (
    <motion.div 
      initial={{ y: 120 }}
      animate={{ y: 0 }}
      className="fixed bottom-0 left-0 right-0 glass border-t border-white/5 p-4 z-50 flex items-center justify-between px-12 h-28 bg-zinc-950/80 backdrop-blur-3xl shadow-[0_-20px_50px_rgba(0,0,0,0.5)]"
    >
      <audio ref={audioRef} />
      
      {/* Song Info */}
      <div className="flex items-center gap-6 w-1/4 min-w-[300px]">
        <div className="w-20 h-20 rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-zinc-900 shrink-0 relative group">
          {artUrl ? (
            <img src={artUrl} alt={currentSong.title} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-zinc-700">
              <Music size={32} />
            </div>
          )}
          <div className="absolute inset-0 bg-indigo-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
        <div className="min-w-0">
          <h4 className="font-black text-white text-lg truncate tracking-tighter leading-tight mb-1">{currentSong.title}</h4>
          <p className="text-[10px] font-black text-zinc-500 truncate uppercase tracking-[0.2em]">{currentSong.artist} • {currentSong.album}</p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-col items-center gap-4 flex-1 max-w-2xl px-8">
        <div className="flex items-center gap-10">
          <button onClick={prevSong} className="text-zinc-500 hover:text-white transition-all hover:scale-110 active:scale-90">
            <SkipBack size={28} fill="currentColor" />
          </button>
          <button 
            onClick={togglePlay}
            className="w-14 h-14 bg-white text-zinc-950 rounded-full flex items-center justify-center hover:scale-110 active:scale-90 transition-all shadow-[0_0_30px_rgba(255,255,255,0.2)]"
          >
            {isPlaying ? <Pause size={30} fill="currentColor" /> : <Play size={30} fill="currentColor" className="ml-1" />}
          </button>
          <button onClick={nextSong} className="text-zinc-500 hover:text-white transition-all hover:scale-110 active:scale-90">
            <SkipForward size={28} fill="currentColor" />
          </button>
        </div>
        <div className="w-full flex items-center gap-4">
            <span className="text-[10px] font-black text-zinc-600 w-12 text-right tabular-nums tracking-widest">
                {formatTime(currentTime)}
            </span>
            <div className="flex-1 relative h-6 flex items-center group/progress">
                <input 
                    type="range" 
                    min="0" 
                    max={duration || 0} 
                    step="0.1"
                    value={currentTime}
                    onChange={handleProgressChange}
                    className="w-full h-1 bg-white/5 rounded-full appearance-none cursor-pointer accent-indigo-500 hover:h-1.5 transition-all"
                />
            </div>
            <span className="text-[10px] font-black text-zinc-600 w-12 tabular-nums tracking-widest">
                {formatTime(duration)}
            </span>
        </div>
      </div>

      {/* Actions: Sonos Cast & Volume */}
      <div className="flex items-center justify-end gap-10 w-1/4">
        <div className="relative">
            <button 
                onClick={() => {
                    setIsCastMenuOpen(!isCastMenuOpen);
                    if (!isCastMenuOpen) discoverDevices();
                }}
                className={cn(
                    "p-3 rounded-2xl transition-all border shadow-xl active:scale-90",
                    activeCastIP ? "bg-indigo-600 border-indigo-500 text-white shadow-indigo-500/30" : "bg-white/5 border-white/5 text-zinc-400 hover:bg-white/10 hover:border-white/10"
                )}
            >
                <Cast size={22} />
            </button>

            <AnimatePresence>
                {isCastMenuOpen && (
                    <motion.div 
                        initial={{ opacity: 0, y: 20, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 20, scale: 0.95 }}
                        className="absolute bottom-full right-0 mb-6 w-72 glass border border-white/10 rounded-[2rem] shadow-[0_20px_50px_rgba(0,0,0,0.5)] p-3 overflow-hidden bg-zinc-900/90 backdrop-blur-3xl"
                    >
                        <div className="px-5 py-4 border-b border-white/5 mb-2">
                            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-indigo-400">Cast to Speaker</p>
                        </div>
                        {isDiscovering ? (
                            <div className="p-10 text-center">
                                <Loader2 size={28} className="animate-spin mx-auto text-indigo-500 mb-3" />
                                <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Scanning...</p>
                            </div>
                        ) : (
                            <div className="space-y-1 max-h-64 overflow-y-auto custom-scrollbar">
                                {devices.map(d => (
                                    <button 
                                        key={d.ip}
                                        onClick={() => castToDevice(d)}
                                        className={cn(
                                            "w-full flex items-center gap-4 px-5 py-4 rounded-2xl transition-all text-left group",
                                            activeCastIP === d.ip ? "bg-indigo-600/20 text-indigo-400" : "hover:bg-white/5 text-zinc-300"
                                        )}
                                    >
                                        <Speaker size={18} className={cn(activeCastIP === d.ip ? "text-indigo-500" : "text-zinc-500 group-hover:text-indigo-400")} />
                                        <span className="flex-1 font-black text-xs uppercase tracking-widest">{d.name}</span>
                                        {activeCastIP === d.ip && <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse shadow-[0_0_8px_rgba(99,102,241,0.5)]" />}
                                    </button>
                                ))}
                                {devices.length === 0 && !isDiscovering && (
                                    <div className="p-8 text-center opacity-30">
                                        <Speaker size={32} className="mx-auto mb-2" />
                                        <p className="text-[10px] font-black uppercase tracking-widest">No matrix nodes</p>
                                    </div>
                                )}
                                {activeCastIP && (
                                    <button 
                                        onClick={stopCasting}
                                        className="w-full mt-3 px-5 py-4 text-[10px] font-black uppercase tracking-[0.2em] text-red-500 hover:bg-red-500/10 rounded-2xl transition-all border border-transparent hover:border-red-500/20"
                                    >
                                        Disconnect
                                    </button>
                                )}
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>

        <div className="flex items-center gap-4 text-zinc-500 group bg-white/5 px-5 py-3 rounded-2xl border border-white/5">
            <Volume2 size={20} className="group-hover:text-indigo-400 transition-colors" />
            <input 
                type="range" 
                min="0" 
                max="100"
                value={volume}
                onChange={handleVolumeChange}
                className="w-32 h-1 bg-white/10 rounded-full appearance-none cursor-pointer accent-indigo-500"
            />
        </div>
      </div>
    </motion.div>
  );
}

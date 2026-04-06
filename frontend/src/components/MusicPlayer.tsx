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
      audioRef.current.src = `http://192.168.1.100:8000/stream/${currentSong.id}`;
      // If we are currently casting, update the cast device instead of local play
      if (activeCastIP) {
        const device = devices.find(d => d.ip === activeCastIP);
        if (device) {
            castToDevice(device);
        } else {
            // Fallback if device list is lost
            fetch("http://192.168.1.100:8000/sonos/play", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ip: activeCastIP, song_id: currentSong.id }),
            });
        }
      } else if (isPlaying) {
        audioRef.current.play().catch(console.error);
      }
    }
  }, [currentSong]);

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
                    if (data.state === "STOPPED" || data.state === "PAUSED_PLAYBACK") {
                        // Keep in sync if speaker was stopped externally
                        // setIsPlaying(false);
                    }
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

  return (
    <motion.div 
      initial={{ y: 100 }}
      animate={{ y: 0 }}
      className="fixed bottom-0 left-0 right-0 glass border-t border-white/10 p-4 z-50 flex items-center justify-between px-8 md:px-12 h-24"
    >
      <audio ref={audioRef} />
      
      {/* Song Info */}
      <div className="flex items-center gap-4 w-1/3">
        <div className="w-16 h-16 rounded-xl overflow-hidden shadow-lg border border-white/10 bg-zinc-800 shrink-0">
          {currentSong.album_art_url ? (
            <img src={currentSong.album_art_url} alt={currentSong.title} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-zinc-500">
              <Music size={24} />
            </div>
          )}
        </div>
        <div className="min-w-0">
          <h4 className="font-black text-slate-100 truncate tracking-tight">{currentSong.title}</h4>
          <p className="text-[10px] font-bold text-zinc-500 truncate uppercase tracking-widest">{currentSong.artist} • {currentSong.album}</p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-col items-center gap-2 w-1/3">
        <div className="flex items-center gap-6">
          <button onClick={prevSong} className="text-zinc-400 hover:text-indigo-500 transition-colors">
            <SkipBack size={24} fill="currentColor" />
          </button>
          <button 
            onClick={togglePlay}
            className="w-12 h-12 bg-white text-zinc-900 rounded-full flex items-center justify-center hover:scale-110 active:scale-95 transition-all shadow-xl"
          >
            {isPlaying ? <Pause size={24} fill="currentColor" /> : <Play size={24} fill="currentColor" className="ml-1" />}
          </button>
          <button onClick={nextSong} className="text-zinc-400 hover:text-indigo-500 transition-colors">
            <SkipForward size={24} fill="currentColor" />
          </button>
        </div>
        <div className="w-full flex items-center gap-3 px-4">
            <span className="text-[9px] font-black text-zinc-500 w-10 text-right tabular-nums">
                {formatTime(currentTime)}
            </span>
            <input 
                type="range" 
                min="0" 
                max={duration || 0} 
                step="0.1"
                value={currentTime}
                onChange={handleProgressChange}
                className="flex-1 h-1 bg-zinc-800 rounded-full appearance-none cursor-pointer accent-indigo-500"
            />
            <span className="text-[9px] font-black text-zinc-500 w-10 tabular-nums">
                {formatTime(duration)}
            </span>
        </div>
      </div>

      {/* Actions: Sonos Cast & Volume */}
      <div className="flex items-center justify-end gap-6 w-1/3">
        <div className="relative">
            <button 
                onClick={() => {
                    setIsCastMenuOpen(!isCastMenuOpen);
                    if (!isCastMenuOpen) discoverDevices();
                }}
                className={cn(
                    "p-2.5 rounded-xl transition-all border",
                    activeCastIP ? "bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-500/20" : "bg-white/5 border-white/5 text-zinc-400 hover:bg-white/10"
                )}
            >
                <Cast size={20} />
            </button>

            <AnimatePresence>
                {isCastMenuOpen && (
                    <motion.div 
                        initial={{ opacity: 0, y: 10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 10, scale: 0.95 }}
                        className="absolute bottom-full right-0 mb-4 w-64 glass border border-white/10 rounded-2xl shadow-2xl p-2 overflow-hidden"
                    >
                        <div className="px-4 py-3 border-b border-white/5 mb-2">
                            <p className="text-[10px] font-black uppercase tracking-widest text-indigo-500">Available Speakers</p>
                        </div>
                        {isDiscovering ? (
                            <div className="p-8 text-center">
                                <Loader2 size={24} className="animate-spin mx-auto text-zinc-500 mb-2" />
                                <p className="text-[10px] font-bold text-zinc-500 uppercase">Scanning Network...</p>
                            </div>
                        ) : (
                            <div className="space-y-1">
                                {devices.map(d => (
                                    <button 
                                        key={d.ip}
                                        onClick={() => castToDevice(d)}
                                        className={cn(
                                            "w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-left group",
                                            activeCastIP === d.ip ? "bg-indigo-600/20 text-indigo-400" : "hover:bg-white/5 text-zinc-300"
                                        )}
                                    >
                                        <Speaker size={16} />
                                        <span className="flex-1 font-bold text-xs">{d.name}</span>
                                        {activeCastIP === d.ip && <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />}
                                    </button>
                                ))}
                                {devices.length === 0 && !isDiscovering && (
                                    <p className="p-6 text-center text-[10px] font-bold text-zinc-600 uppercase">No speakers found</p>
                                )}
                                {activeCastIP && (
                                    <button 
                                        onClick={stopCasting}
                                        className="w-full mt-2 px-4 py-3 text-[10px] font-black uppercase tracking-widest text-red-500 hover:bg-red-500/10 rounded-xl transition-all"
                                    >
                                        Stop Casting
                                    </button>
                                )}
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>

        <div className="flex items-center gap-3 text-zinc-400 group">
            <Volume2 size={20} className="group-hover:text-indigo-500 transition-colors" />
            <input 
                type="range" 
                min="0" 
                max="100"
                value={volume}
                onChange={handleVolumeChange}
                className="w-24 h-1 bg-zinc-800 rounded-full appearance-none cursor-pointer accent-indigo-500"
            />
        </div>
      </div>
    </motion.div>
  );
}

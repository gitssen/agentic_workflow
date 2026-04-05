"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Play, Pause, SkipBack, SkipForward, Volume2, Music } from "lucide-react";
import { motion } from "framer-motion";

interface Song {
  id: string;
  title: string;
  artist: string;
  album: string;
  album_art_url?: string;
}

interface MusicPlayerProps {
  currentSong: Song | null;
  playlist: Song[];
  onNext: () => void;
  onPrev: () => void;
}

export default function MusicPlayer({ currentSong, onNext, onPrev }: MusicPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const formatTime = (time: number) => {
    if (isNaN(time)) return "0:00";
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    if (currentSong && audioRef.current) {
      audioRef.current.src = `http://localhost:8000/stream/${currentSong.id}`;
      if (isPlaying) {
        audioRef.current.play().catch(console.error);
      }
    }
  }, [currentSong, isPlaying]);

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
    audio.addEventListener("ended", onNext);

    return () => {
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("ended", onNext);
    };
  }, [handleTimeUpdate, handleLoadedMetadata, onNext]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch(console.error);
    }
    setIsPlaying(!isPlaying);
  };

  const handleProgressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
    setCurrentTime(newTime);
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
          <h4 className="font-black text-slate-100 truncate">{currentSong.title}</h4>
          <p className="text-xs font-bold text-zinc-500 truncate">{currentSong.artist} • {currentSong.album}</p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-col items-center gap-2 w-1/3">
        <div className="flex items-center gap-6">
          <button onClick={onPrev} className="text-zinc-400 hover:text-indigo-500 transition-colors">
            <SkipBack size={24} fill="currentColor" />
          </button>
          <button 
            onClick={togglePlay}
            className="w-12 h-12 bg-white text-zinc-900 rounded-full flex items-center justify-center hover:scale-110 active:scale-95 transition-all shadow-xl"
          >
            {isPlaying ? <Pause size={24} fill="currentColor" /> : <Play size={24} fill="currentColor" className="ml-1" />}
          </button>
          <button onClick={onNext} className="text-zinc-400 hover:text-indigo-500 transition-colors">
            <SkipForward size={24} fill="currentColor" />
          </button>
        </div>
        <div className="w-full flex items-center gap-3">
            <span className="text-[10px] font-black text-zinc-500 w-10 text-right">
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
            <span className="text-[10px] font-black text-zinc-500 w-10">
                {formatTime(duration)}
            </span>
        </div>
      </div>

      {/* Volume (Placeholder) */}
      <div className="flex items-center justify-end gap-3 w-1/3 text-zinc-400">
        <Volume2 size={20} />
        <div className="w-24 h-1 bg-zinc-800 rounded-full overflow-hidden">
            <div className="w-2/3 h-full bg-indigo-500" />
        </div>
      </div>
    </motion.div>
  );
}

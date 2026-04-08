"use client";

import React, { createContext, useContext, useState, useCallback, useEffect } from "react";

interface Song {
  id: string;
  title: string;
  artist: string;
  album: string;
  album_art_url?: string;
}

interface MusicContextType {
  currentSong: Song | null;
  playlist: Song[];
  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;
  setCurrentSong: (song: Song | null) => void;
  setPlaylist: (songs: Song[]) => void;
  nextSong: () => void;
  prevSong: () => void;
  playSong: (songs: Song[], index: number) => void;
}

const MusicContext = createContext<MusicContextType | undefined>(undefined);

export function MusicProvider({ children }: { children: React.ReactNode }) {
  const [currentSong, setCurrentSong] = useState<Song | null>(null);
  const [playlist, setPlaylist] = useState<Song[]>([]);
  const [isPlaying, setIsPlaying] = useState(false);

  const nextSong = useCallback(() => {
    if (!currentSong || playlist.length === 0) return;
    const idx = playlist.findIndex(s => s.id === currentSong.id);
    if (idx !== -1 && idx < playlist.length - 1) {
      setCurrentSong(playlist[idx + 1]);
    }
  }, [currentSong, playlist]);

  const prevSong = useCallback(() => {
    if (!currentSong || playlist.length === 0) return;
    const idx = playlist.findIndex(s => s.id === currentSong.id);
    if (idx > 0) {
      setCurrentSong(playlist[idx - 1]);
    }
  }, [currentSong, playlist]);

  const playSong = useCallback((songs: Song[], index: number) => {
    setPlaylist(songs);
    setCurrentSong(songs[index]);
    setIsPlaying(true);
  }, []);

  // Handle browser close/refresh confirmation
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isPlaying) {
        e.preventDefault();
        e.returnValue = "Music is currently playing. Are you sure you want to leave?";
        return e.returnValue;
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isPlaying]);

  return (
    <MusicContext.Provider value={{ 
      currentSong, playlist, isPlaying, setIsPlaying, 
      setCurrentSong, setPlaylist, nextSong, prevSong, playSong 
    }}>
      {children}
    </MusicContext.Provider>
  );
}

export function useMusic() {
  const context = useContext(MusicContext);
  if (context === undefined) {
    throw new Error("useMusic must be used within a MusicProvider");
  }
  return context;
}

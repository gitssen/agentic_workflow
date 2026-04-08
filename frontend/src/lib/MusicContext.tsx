"use client";

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";

interface Song {
  id: string;
  title: string;
  artist: string;
  album: string;
  album_art_url?: string;
  albumArtUrl?: string; // Support both naming conventions
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

const BASE_URL = "http://192.168.1.100:8000";

export function MusicProvider({ children }: { children: React.ReactNode }) {
  const [currentSong, setCurrentSongState] = useState<Song | null>(null);
  const [playlist, setPlaylistState] = useState<Song[]>([]);
  const [isPlaying, setIsPlayingState] = useState(false);
  const lastSyncRef = useRef<number>(0);

  // Sync state TO backend
  const syncToBackend = useCallback(async (song: Song | null, playing: boolean, list: Song[]) => {
    try {
      await fetch(`${BASE_URL}/music/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_song: song,
          is_playing: playing,
          playlist: list
        }),
      });
      // Store current time in seconds (matching backend time.time())
      lastSyncRef.current = Date.now() / 1000;
    } catch (e) {
      console.error("Failed to sync to backend", e);
    }
  }, []);

  // Sync state FROM backend
  const syncFromBackend = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}/music/state`);
      if (res.ok) {
        const data = await res.json();
        // Update only if backend timestamp is newer than our last sync
        // Using a 0.5s buffer to prevent self-echo loops
        if (data.last_updated > (lastSyncRef.current + 0.1)) {
          setCurrentSongState(data.current_song);
          setIsPlayingState(data.is_playing);
          setPlaylistState(data.playlist || []);
          lastSyncRef.current = data.last_updated;
        }
      }
    } catch (e) {
      // Quiet fail if backend is down
    }
  }, []);

  // Increase polling frequency to 1s for better responsiveness
  useEffect(() => {
    const interval = setInterval(syncFromBackend, 1000);
    return () => clearInterval(interval);
  }, [syncFromBackend]);

  const setCurrentSong = (song: Song | null) => {
    setCurrentSongState(song);
    syncToBackend(song, isPlaying, playlist);
  };

  const setIsPlaying = (playing: boolean) => {
    setIsPlayingState(playing);
    syncToBackend(currentSong, playing, playlist);
  };

  const setPlaylist = (songs: Song[]) => {
    setPlaylistState(songs);
    syncToBackend(currentSong, isPlaying, songs);
  };

  const playSong = useCallback((songs: Song[], index: number) => {
    const song = songs[index];
    setPlaylistState(songs);
    setCurrentSongState(song);
    setIsPlayingState(true);
    syncToBackend(song, true, songs);
  }, [syncToBackend]);

  const nextSong = useCallback(() => {
    if (!currentSong || playlist.length === 0) return;
    const idx = playlist.findIndex(s => s.id === currentSong.id);
    if (idx !== -1 && idx < playlist.length - 1) {
      const next = playlist[idx + 1];
      setCurrentSongState(next);
      syncToBackend(next, isPlaying, playlist);
    }
  }, [currentSong, playlist, isPlaying, syncToBackend]);

  const prevSong = useCallback(() => {
    if (!currentSong || playlist.length === 0) return;
    const idx = playlist.findIndex(s => s.id === currentSong.id);
    if (idx > 0) {
      const prev = playlist[idx - 1];
      setCurrentSongState(prev);
      syncToBackend(prev, isPlaying, playlist);
    }
  }, [currentSong, playlist, isPlaying, syncToBackend]);

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

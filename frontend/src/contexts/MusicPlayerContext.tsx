import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useConfig } from "./ConfigContext";
import { claimAudio, onAudioOwnerChange, releaseAudio } from "../utils/audioLock";

export type MusicTrack = {
    id: string;
    title: string;
    url: string;
    source: string;
    source_name: string;
};

export type RepeatMode = "off" | "one" | "all";

export type MusicPlayerSettings = {
    /** The tracks the user added — the player shows nothing else. */
    favorites: MusicTrack[];
    /** Ids of the favourites that play in the background loop. */
    playlist: string[];
    repeat: RepeatMode;
    volume: number;
    autoplay: boolean;
};

const DEFAULT_SETTINGS: MusicPlayerSettings = {
    favorites: [],
    playlist: [],
    repeat: "all",
    volume: 0.5,
    autoplay: false,
};

type MusicPlayerContextType = {
    settings: MusicPlayerSettings;
    currentId: string | null;
    playing: boolean;
    open: boolean;
    setOpen: (value: boolean) => void;
    playTrack: (id: string) => void;
    togglePlay: () => void;
    stop: () => void;
    next: () => void;
    prev: () => void;
    time: number;
    duration: number;
    seekTo: (ratio: number) => void;
    isFavorite: (id: string) => void | boolean;
    toggleFavorite: (id: string) => void;
    inPlaylist: (id: string) => void | boolean;
    toggleInPlaylist: (id: string) => void;
    setRepeat: (mode: RepeatMode) => void;
    setVolume: (value: number) => void;
    setAutoplay: (value: boolean) => void;
    clearPlaylist: () => void;
    /** Add a track by hand (from a music player inside the book). */
    addTrack: (track: Partial<MusicTrack> & { url: string }) => void;
    current: MusicTrack | null;
    /** All tracks the user added (favourites), in the order they were added. */
    tracks: MusicTrack[];
};

const MusicPlayerContext = createContext<MusicPlayerContextType | undefined>(undefined);

const trackId = (raw: any): string => String(raw?.id || raw?.url || raw?.title || "").trim();

const normalizeTrack = (raw: any): MusicTrack | null => {
    if (!raw || typeof raw !== "object") return null;
    const url = String(raw.url || "").trim();
    if (!url) return null;
    return {
        id: trackId(raw) || url,
        title: String(raw.title || raw.source_name || url),
        url,
        source: String(raw.source || "manual"),
        source_name: String(raw.source_name || ""),
    };
};

const readSettings = (raw: any): MusicPlayerSettings => {
    const src = raw && typeof raw === "object" ? raw : {};
    const favorites: MusicTrack[] = [];
    const seen = new Set<string>();
    const rawFavorites = Array.isArray(src.favorites) ? src.favorites : [];
    for (const item of rawFavorites) {
        // Old format: only the file id was stored. Without the URL the track
        // cannot be played, so it is dropped.
        const track = normalizeTrack(item);
        if (!track || seen.has(track.id)) continue;
        seen.add(track.id);
        favorites.push(track);
    }
    const known = new Set(favorites.map((t) => t.id));
    const playlist = (Array.isArray(src.playlist) ? src.playlist : [])
        .map((id: any) => String(id))
        .filter((id: string) => known.has(id));
    const volume = Number(src.volume);
    return {
        favorites,
        playlist,
        repeat: (src.repeat === "off" || src.repeat === "one" || src.repeat === "all") ? src.repeat : "all",
        volume: Number.isFinite(volume) ? Math.min(1, Math.max(0, volume)) : DEFAULT_SETTINGS.volume,
        autoplay: !!src.autoplay,
    };
};

/** The built-in player: the tracks the user collected from the book, the
 *  playlist that loops in the background and the repeat modes. The state
 *  lives in the macro config, so it survives a restart of the panel. */
export function MusicPlayerProvider({ children }: { children: ReactNode }) {
    const { config, saveConfig } = useConfig();
    const [settings, setSettings] = useState<MusicPlayerSettings>(DEFAULT_SETTINGS);
    const [settingsLoaded, setSettingsLoaded] = useState(false);
    const [currentId, setCurrentId] = useState<string | null>(null);
    const [playing, setPlaying] = useState(false);
    const [open, setOpen] = useState(false);
    const [time, setTime] = useState(0);
    const [duration, setDuration] = useState(0);
    // Bumped when the current track has to start from the top again. The
    // loader effect only watches the track id, so restarting the same track
    // needs a second signal.
    const [reloadToken, setReloadToken] = useState(0);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const ownerId = "music-player";

    // Load the settings from the config once it is there.
    useEffect(() => {
        if (!config) return;
        setSettings(readSettings((config as any).music_player));
        setSettingsLoaded(true);
    }, [config]);

    const persist = useCallback((next: MusicPlayerSettings) => {
        setSettings(next);
        if (!config) return;
        void saveConfig({ ...(config as any), music_player: next } as any);
    }, [config, saveConfig]);

    const tracks = useMemo(() => settings.favorites, [settings.favorites]);
    const trackById = useMemo(() => {
        const map = new Map<string, MusicTrack>();
        tracks.forEach((t) => map.set(t.id, t));
        return map;
    }, [tracks]);
    // The playing track is looked up through a ref: the effect must only
    // restart when the track CHANGES. Re-reading the settings (saving a
    // favourite, for example) must not interrupt the playback.
    const trackByIdRef = useRef(trackById);
    trackByIdRef.current = trackById;

    const current = currentId ? (trackById.get(currentId) || null) : null;

    /** Start a track from the top. The previous one is stopped right away —
     *  otherwise it keeps playing while the new file is still being fetched. */
    const playTrack = useCallback((id: string) => {
        const track = trackById.get(id);
        if (!track) return;
        const el = audioRef.current;
        if (el) {
            try { el.pause(); } catch { /* ignore */ }
        }
        setCurrentId(id);
        setPlaying(true);
        // The loader only reacts to a changed track, so the same track has to
        // ask for a restart on its own.
        setReloadToken((t) => t + 1);
    }, [trackById]);

    const stop = useCallback(() => {
        setPlaying(false);
        const el = audioRef.current;
        if (el) {
            try { el.pause(); } catch { /* ignore */ }
        }
    }, []);

    /** Pause and resume. A paused track keeps its position and picks up
     *  where it left off — only a track that was never loaded (or whose file
     *  is gone) starts from the top. */
    const togglePlay = useCallback(() => {
        if (playing) { stop(); return; }
        const id = currentId || settings.playlist[0] || tracks[0]?.id;
        if (!id) return;
        const el = audioRef.current;
        if (currentId && el && el.src) {
            try {
                const p = el.play();
                if (p && typeof (p as any).then === "function") {
                    (p as Promise<void>)
                        .then(() => { setPlaying(true); claimAudio(ownerId); })
                        .catch(() => { setPlaying(false); });
                } else {
                    setPlaying(true);
                    claimAudio(ownerId);
                }
                return;
            } catch { /* fall through and start the track over */ }
        }
        playTrack(id);
    }, [playing, stop, currentId, settings.playlist, tracks, playTrack]);

    const playlistTracks = useMemo(
        () => settings.playlist.map((id) => trackById.get(id)).filter(Boolean) as MusicTrack[],
        [settings.playlist, trackById],
    );

    const next = useCallback(() => {
        const list = playlistTracks.length ? playlistTracks : tracks;
        if (!list.length) return;
        const idx = list.findIndex((t) => t.id === currentId);
        const target = idx < 0 ? list[0] : list[(idx + 1) % list.length];
        playTrack(target.id);
    }, [playlistTracks, tracks, currentId, playTrack]);

    const prev = useCallback(() => {
        const list = playlistTracks.length ? playlistTracks : tracks;
        if (!list.length) return;
        const idx = list.findIndex((t) => t.id === currentId);
        const target = idx <= 0 ? list[list.length - 1] : list[idx - 1];
        playTrack(target.id);
    }, [playlistTracks, tracks, currentId, playTrack]);

    const isFavorite = useCallback((id: string) => settings.favorites.some((t) => t.id === id), [settings.favorites]);
    const toggleFavorite = useCallback((id: string) => {
        const track = trackById.get(id);
        if (!track) return;
        const favorites = settings.favorites.filter((t) => t.id !== id);
        const playlist = settings.playlist.filter((x) => x !== id);
        persist({ ...settings, favorites, playlist });
    }, [settings, persist, trackById]);

    const inPlaylist = useCallback((id: string) => settings.playlist.includes(id), [settings.playlist]);
    const toggleInPlaylist = useCallback((id: string) => {
        if (!trackById.has(id)) return;
        const playlist = settings.playlist.includes(id)
            ? settings.playlist.filter((x) => x !== id)
            : [...settings.playlist, id];
        persist({ ...settings, playlist });
    }, [settings, persist, trackById]);

    const setRepeat = useCallback((mode: RepeatMode) => persist({ ...settings, repeat: mode }), [settings, persist]);
    const setVolume = useCallback((value: number) => persist({ ...settings, volume: value }), [settings, persist]);
    const setAutoplay = useCallback((value: boolean) => persist({ ...settings, autoplay: value }), [settings, persist]);
    const clearPlaylist = useCallback(() => persist({ ...settings, playlist: [] }), [settings, persist]);

    /** Add a track by hand (from a music player inside the book). It goes
     *  into the favourites; the user picks from there what loops in the
     *  background. Adding the same track twice does nothing. */
    const addTrack = useCallback((track: Partial<MusicTrack> & { url: string }) => {
        const full = normalizeTrack(track);
        if (!full) return;
        if (settings.favorites.some((t) => t.id === full.id || t.url === full.url)) return;
        persist({ ...settings, favorites: [...settings.favorites, full] });
    }, [settings, persist]);

    useEffect(() => {
        const el = audioRef.current;
        if (!el) return;
        el.volume = Math.min(1, Math.max(0, settings.volume));
    }, [settings.volume]);

    // Load the file through the local media cache and start it. It only runs
    // when the track changes, or when the same track is restarted on purpose.
    useEffect(() => {
        const el = audioRef.current;
        if (!el || !currentId) return;
        const track = trackByIdRef.current.get(currentId);
        if (!track) return;
        let alive = true;
        // Drop the previous file so the old track cannot keep playing while
        // the new one is still being fetched.
        try {
            el.pause();
            el.removeAttribute("src");
            el.load();
        } catch { /* ignore */ }
        setTime(0);
        setDuration(0);
        void (async () => {
            let src = track.url;
            try {
                const res: any = await window.pywebview?.api?.ensure_media_cached?.(track.url);
                if (alive && res?.success && res.local_url) src = String(res.local_url);
            } catch { /* stream it directly */ }
            if (!alive) return;
            el.src = src;
            el.loop = false;
            try { await el.play(); } catch { setPlaying(false); }
        })();
        return () => { alive = false; };
    }, [currentId, reloadToken]);

    /** Move the playhead of the current track (0..1). */
    const seekTo = useCallback((ratio: number) => {
        const el = audioRef.current;
        if (!el || !Number.isFinite(el.duration) || el.duration <= 0) return;
        const value = Math.min(1, Math.max(0, ratio)) * el.duration;
        el.currentTime = value;
        setTime(value);
    }, []);

    // The end of a track: repeat the same one, walk the playlist, or stop.
    const onEnded = useCallback(() => {
        if (settings.repeat === "one") {
            const el = audioRef.current;
            if (el) { try { el.currentTime = 0; void el.play(); } catch { /* ignore */ } }
            return;
        }
        const list = playlistTracks.length ? playlistTracks : tracks;
        if (!list.length) { setPlaying(false); return; }
        if (settings.repeat === "off" && playlistTracks.length <= 1) { setPlaying(false); return; }
        const idx = list.findIndex((t) => t.id === currentId);
        const target = idx < 0 ? list[0] : list[(idx + 1) % list.length];
        playTrack(target.id);
    }, [settings.repeat, playlistTracks, tracks, currentId, playTrack]);

    // Only one sound at a time: the book players and this player share one
    // slot, so a track started somewhere else pauses this one.
    useEffect(() => onAudioOwnerChange((id) => {
        if (!id || id === ownerId) return;
        const el = audioRef.current;
        if (el && !el.paused) {
            try { el.pause(); } catch { /* ignore */ }
        }
        setPlaying(false);
    }), []);

    // Background playback once the panel is fully up: the settings have to be
    // read from the config first, otherwise the toggle would still look off
    // and the playlist would never start.
    useEffect(() => {
        if (!config || !settingsLoaded) return;
        if (!settings.autoplay) return;
        if (currentId) return; // something is already playing
        const first = settings.playlist[0] || settings.favorites[0]?.id;
        if (first) playTrack(first);
    }, [config, settingsLoaded, settings.autoplay, settings.playlist, settings.favorites, currentId, playTrack]);

    const value = useMemo<MusicPlayerContextType>(() => ({
        settings, currentId, playing, open, setOpen,
        playTrack, togglePlay, stop, next, prev,
        time, duration, seekTo,
        isFavorite, toggleFavorite, inPlaylist, toggleInPlaylist,
        setRepeat, setVolume, setAutoplay, clearPlaylist, addTrack, current, tracks,
    }), [settings, currentId, playing, open, playTrack, togglePlay, stop, next, prev,
        time, duration, seekTo, isFavorite, toggleFavorite, inPlaylist, toggleInPlaylist,
        setRepeat, setVolume, setAutoplay, clearPlaylist, addTrack, current, tracks]);

    return (
        <MusicPlayerContext.Provider value={value}>
            {children}
            <audio
                ref={audioRef}
                onEnded={onEnded}
                onPlay={() => { setPlaying(true); claimAudio(ownerId); }}
                onPause={() => { setPlaying(false); releaseAudio(ownerId); }}
                onTimeUpdate={(e) => {
                    setTime(e.currentTarget.currentTime);
                    if (Number.isFinite(e.currentTarget.duration)) setDuration(e.currentTarget.duration);
                }}
                onLoadedMetadata={(e) => {
                    if (Number.isFinite(e.currentTarget.duration)) setDuration(e.currentTarget.duration);
                }}
                style={{ display: "none" }}
            />
        </MusicPlayerContext.Provider>
    );
}

export function useMusicPlayer(): MusicPlayerContextType {
    const context = useContext(MusicPlayerContext);
    if (context === undefined) {
        throw new Error("useMusicPlayer must be used within a MusicPlayerProvider");
    }
    return context;
}

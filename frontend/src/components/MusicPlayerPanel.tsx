import { useMemo, useState } from "react";
import { useMusicPlayer } from "../contexts/MusicPlayerContext";
import type { MusicTrack } from "../contexts/MusicPlayerContext";

const REPEAT_LABELS: Record<string, string> = { off: "No repeat", one: "Repeat one", all: "Repeat all" };

const fmtTime = (t: number) => {
    if (!Number.isFinite(t) || t < 0) return "0:00";
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
};

/** The built-in player: the tracks collected from Sol's Book. The starred
 *  ones are the collection, the playlist is the part that loops in the
 *  background. It hangs from the top-right corner, next to its button. */
export default function MusicPlayerPanel() {
    const player = useMusicPlayer();
    const [filter, setFilter] = useState<"favorites" | "playlist">("favorites");
    const [query, setQuery] = useState("");

    const visible = useMemo<MusicTrack[]>(() => {
        let list = player.tracks;
        if (filter === "playlist") {
            const order = player.settings.playlist;
            list = order
                .map((id) => player.tracks.find((t) => t.id === id))
                .filter(Boolean) as MusicTrack[];
        }
        const q = query.trim().toLowerCase();
        if (q) list = list.filter((t) => t.title.toLowerCase().includes(q) || t.source_name.toLowerCase().includes(q));
        return list;
    }, [player.tracks, player.settings.playlist, filter, query]);

    if (!player.open) return null;

    const seek = (e: React.MouseEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect();
        player.seekTo((e.clientX - rect.left) / rect.width);
    };

    const progress = player.duration > 0 ? Math.min(100, (player.time / player.duration) * 100) : 0;

    return (
        <div
            onClick={() => player.setOpen(false)}
            style={{ position: "fixed", inset: 0, zIndex: 10000 }}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                className="card"
                style={{
                    position: "absolute", top: 12, right: 12,
                    width: "min(420px, calc(100vw - 24px))",
                    maxHeight: "calc(100vh - 24px)",
                    display: "flex", flexDirection: "column", padding: 0,
                    boxShadow: "0 18px 48px -18px rgba(0,0,0,.9)",
                }}
            >
                <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                        <div className="card-icon">🎵</div>
                        <div style={{ minWidth: 0 }}>
                            <h3 style={{ margin: 0, fontSize: 14 }}>Music player</h3>
                            <p style={{ margin: 0, fontSize: 11, color: "var(--text-secondary)" }}>
                                {player.tracks.length} collected · {player.settings.playlist.length} in the playlist
                            </p>
                        </div>
                    </div>
                    <button className="btn" onClick={() => player.setOpen(false)} title="Close">✕</button>
                </div>

                {/* Now playing + seek bar */}
                <div style={{ padding: "12px 14px", borderBottom: "1px solid rgba(255,255,255,.08)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <button className="btn" onClick={player.togglePlay} style={{ minWidth: 66, fontSize: 12 }} title={player.playing ? "Pause" : "Play"}>
                            {player.playing ? "❚❚ Pause" : "▶ Play"}
                        </button>
                        <div style={{ flex: 1, minWidth: 0, fontSize: 12, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {player.current ? player.current.title : "Nothing playing"}
                        </div>
                    </div>
                    <div
                        onClick={seek}
                        title="Seek"
                        style={{ height: 8, borderRadius: 4, background: "rgba(255,255,255,.10)", border: "1px solid rgba(255,255,255,.12)", cursor: "pointer", position: "relative", overflow: "hidden" }}
                    >
                        <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: `${progress}%`, background: "var(--accent)", transition: "width .12s linear" }} />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, color: "var(--text-muted)", fontVariantNumeric: "tabular-nums", marginTop: 4 }}>
                        <span>{fmtTime(player.time)}</span>
                        <span>{player.duration > 0 ? fmtTime(player.duration) : "-:--"}</span>
                    </div>
                </div>

                {/* Options */}
                <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,.08)", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", fontSize: 11, color: "var(--text-secondary)" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        Repeat
                        <select
                            className="form-input"
                            value={player.settings.repeat}
                            onChange={(e) => player.setRepeat(e.target.value as any)}
                            style={{ fontSize: 11, padding: "3px 6px" }}
                        >
                            {Object.entries(REPEAT_LABELS).map(([value, label]) => (
                                <option key={value} value={value}>{label}</option>
                            ))}
                        </select>
                    </label>
                    <label style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
                        Vol
                        <input
                            type="range" min={0} max={100} value={Math.round(player.settings.volume * 100)}
                            onChange={(e) => player.setVolume(Number(e.target.value) / 100)}
                            style={{ width: 68 }}
                        />
                    </label>
                </div>

                <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,.08)", display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, color: "var(--text-secondary)" }}>
                    <input
                        type="checkbox"
                        id="music-autoplay"
                        checked={player.settings.autoplay}
                        onChange={(e) => player.setAutoplay(e.target.checked)}
                    />
                    <label htmlFor="music-autoplay">Play the playlist in the background after the panel starts</label>
                    {player.settings.playlist.length > 0 && (
                        <button className="btn" style={{ marginLeft: "auto", fontSize: 11 }} onClick={player.clearPlaylist}>Clear the playlist</button>
                    )}
                </div>

                {/* Filters */}
                <div style={{ padding: "10px 14px", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    {([["favorites", "Starred"], ["playlist", "Playlist"]] as const).map(([value, label]) => (
                        <button
                            key={value}
                            className="btn"
                            onClick={() => setFilter(value)}
                            style={{
                                fontSize: 11, padding: "3px 10px",
                                borderColor: filter === value ? "var(--accent)" : undefined,
                                color: filter === value ? "var(--accent)" : undefined,
                            }}
                        >
                            {label}
                        </button>
                    ))}
                    <input
                        className="form-input"
                        placeholder="Search…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        style={{ flex: "1 1 140px", fontSize: 12, padding: "4px 8px", minWidth: 110 }}
                    />
                </div>

                {/* Tracks */}
                <div style={{ overflowY: "auto", padding: "0 8px 10px", minHeight: 110, flex: 1 }}>
                    {visible.length === 0 && (
                        <div className="form-hint" style={{ padding: 12 }}>
                            {player.tracks.length === 0
                                ? "No tracks yet — add them from a music player in Sol's Book (the ＋ button)."
                                : "Nothing here."}
                        </div>
                    )}
                    {visible.map((track) => (
                        <div
                            key={track.id}
                            onClick={() => player.playTrack(track.id)}
                            style={{
                                display: "flex", alignItems: "center", gap: 8, padding: "6px 8px",
                                borderRadius: 4, cursor: "pointer", fontSize: 12.5,
                                background: player.currentId === track.id ? "rgba(124,91,245,.16)" : "transparent",
                            }}
                        >
                            <span style={{ width: 14, color: player.currentId === track.id ? "var(--accent)" : "var(--text-muted)" }}>
                                {player.currentId === track.id && player.playing ? "♫" : "•"}
                            </span>
                            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{track.title}</span>
                            <span style={{ fontSize: 10.5, color: "var(--text-muted)", maxWidth: 110, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{track.source_name}</span>
                            <button
                                className="btn"
                                title={player.inPlaylist(track.id) ? "Remove from the playlist" : "Add to the playlist"}
                                onClick={(e) => { e.stopPropagation(); player.toggleInPlaylist(track.id); }}
                                style={{
                                    padding: "1px 7px", fontSize: 11,
                                    color: player.inPlaylist(track.id) ? "#22c55e" : undefined,
                                }}
                            >
                                {player.inPlaylist(track.id) ? "✓" : "+"}
                            </button>
                            <button
                                className="btn"
                                title="Remove"
                                onClick={(e) => { e.stopPropagation(); player.toggleFavorite(track.id); }}
                                style={{ padding: "1px 7px", fontSize: 12 }}
                            >
                                ✕
                            </button>
                        </div>
                    ))}
                </div>

                <div style={{ padding: "8px 14px", borderTop: "1px solid rgba(255,255,255,.08)", fontSize: 11, color: "var(--text-muted)" }}>
                    Tracks are added from Sol's Book and saved with the macro settings.
                </div>
            </div>
        </div>
    );
}

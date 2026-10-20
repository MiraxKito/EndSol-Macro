/**
 * A single audio slot for the whole panel.
 *
 * Sol's Book has its own music players and the built-in player has one too.
 * Without a lock both could play at the same time and the tracks would be
 * layered on top of each other. Every audio element claims the slot when it
 * starts; every other element pauses itself when the slot changes hands.
 */

let owner: string | null = null;
const listeners = new Set<(id: string | null) => void>();

/** Take the slot. Other players pause themselves. */
export function claimAudio(id: string) {
    if (!id || owner === id) return;
    owner = id;
    listeners.forEach((cb) => {
        try { cb(id); } catch { /* ignore */ }
    });
}

/** Release the slot when this player stops. */
export function releaseAudio(id: string) {
    if (owner === id) owner = null;
}

/** Who owns the slot right now (null = nobody). */
export function audioOwner(): string | null {
    return owner;
}

/** Subscribe to slot changes. Returns an unsubscribe function. */
export function onAudioOwnerChange(cb: (id: string | null) => void): () => void {
    listeners.add(cb);
    return () => { listeners.delete(cb); };
}

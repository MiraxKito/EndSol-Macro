import developerAvatar from "../assets/developer-avatar-square.jpg";
export default function CreditsPage() {
    return (
        <>
            <div className="page-header">
                <h2>Credits</h2>
                <p>EndSol Macro development team</p>
            </div>

            {/* EndSol Developer */}
            <div className="card">
                <div style={{ display: "flex", justifyContent: "center", marginBottom: "16px" }}>
                    <img
                        src={developerAvatar}
                        alt="Mirax Kitoro"
                        style={{
                            width: "140px",
                            height: "140px",
                            objectFit: "cover",
                            objectPosition: "center center",
                            borderRadius: "8px",
                            border: "3px solid var(--accent)",
                            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
                            background: "var(--bg-card)"
                        }}
                        onError={(e) => {
                            e.currentTarget.style.display = 'none';
                        }}
                    />
                </div>

                <div style={{ textAlign: "center", marginBottom: "16px" }}>
                    <h3 style={{ margin: 0 }}>Mirax Kitoro</h3>
                    <p style={{ color: "var(--accent)", margin: "4px 0", fontSize: "14px" }}>EndSol Macro Developer</p>
                    <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>
                        Fork of Coteab Macro — continued development and customization
                    </p>
                </div>
            </div>

            {/* Original Coteab Macro Team */}
            <div className="card">
                <div className="card-header">
                    <div className="card-icon">👥</div>
                    <div>
                        <h3>Coteab Macro — Original Team</h3>
                        <p>The creators of the original macro that EndSol is based on</p>
                    </div>
                </div>

                <div className="credits-list">
                    <div className="credit-item">
                        <div className="credit-avatar">V</div>
                        <div className="credit-info">
                            <ul style={{ margin: 0, paddingLeft: "16px", listStyle: "disc" }}>
                                <li><strong>Vapure/"@criticize."</strong> — Lead Developer, fullstack</li>
                                <li><strong>Akito</strong> — Lead Developer, fullstack</li>
                            </ul>
                        </div>
                    </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", marginTop: "12px" }}>
                    <a href="https://github.com/xVapure/Noteab-Macro" target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontSize: "13px" }}>
                        GitHub: Coteab Macro (original)
                    </a>
                </div>
            </div>

            {/* MaxStellar */}
            <div className="card" style={{ textAlign: "center" }}>
                <div style={{ display: "flex", justifyContent: "center", marginBottom: "12px" }}>
                    <img
                        src="https://avatars.githubusercontent.com/u/93678379?v=4"
                        alt="MaxStellar"
                        style={{
                            width: "100px",
                            height: "100px",
                            objectFit: "cover",
                            borderRadius: "8px",
                            border: "1px solid var(--border)"
                        }}
                    />
                </div>
                <h3>MaxStellar</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>
                    Biome Macro Creator — Inspiration and biome detection logic
                </p>
                <a href="https://www.youtube.com/@maxstellar_" target="_blank" rel="noreferrer"
                    style={{ color: "var(--accent)", textDecoration: "underline", fontSize: "13px" }}>
                    YouTube Channel
                </a>
            </div>

            {/* Extra Credits */}
            <div className="card">
                <div className="card-header">
                    <div className="card-icon">🏅</div>
                    <div>
                        <h3>Extra Credits</h3>
                        <p>Thanks to everyone who contributed</p>
                    </div>
                </div>

                <div style={{
                    padding: "14px 16px",
                    background: "var(--bg-input)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-md)",
                    fontSize: "13px",
                    lineHeight: "1.8",
                    color: "var(--text-secondary)",
                }}>
                    <div>- maxstellar — Inspiration and biome detection logic</div>
                    <div>- Vexthecoder — Icons and assets</div>
                    <div>- Cresqnt, Baz & the Scope Team — Anti-AFK inspiration</div>
                    <div>- rnd.xy, imsomeone — External contributions</div>
                    <div>- Finnerinch — Former developer</div>
                    <div>- .ivelchampion249._30053 — Fishing logic inspiration</div>
                    <div>- All the testers who made this possible</div>
                </div>
            </div>

            {/* Rights and License */}
            <div className="card">
                <div className="card-header">
                    <div className="card-icon">©</div>
                    <div>
                        <h3>Rights and License</h3>
                        <p>Free personal use — redistribution is not permitted</p>
                    </div>
                </div>
                <div style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: "1.7" }}>
                    <div><strong>EndSol Macro © 2026 EndSol Development Team</strong></div>
                    <div style={{ marginTop: "8px" }}>This software is free for personal, non-commercial use. Copying, republishing, selling, sublicensing, or presenting modified versions as an official release is not permitted without written permission.</div>
                    <div style={{ marginTop: "8px", color: "var(--text-muted)", fontSize: "12px" }}>Third-party components remain subject to their respective licenses.</div>
                </div>
            </div>
        </>
    );
}

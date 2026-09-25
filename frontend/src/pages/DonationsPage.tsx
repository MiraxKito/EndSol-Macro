import { useEffect, useState } from "react";

const BOOSTY_URL = "https://boosty.to/eds_mirax/donate";

export default function DonationsPage() {
    const [donators, setDonators] = useState<string>("Loading supporters list...");

    useEffect(() => {
        fetch("https://raw.githubusercontent.com/MiraxKito/EndSol-Macro/main/assets/appreciation_list.txt")
            .then(res => res.ok ? res.text() : Promise.reject(new Error(String(res.status))))
            .then(text => setDonators(text || "(No entries yet)"))
            .catch(() => setDonators("(No entries yet)"));
    }, []);

    return (
        <>
            <div className="page-header">
                <h2>Donations {"<3"}</h2>
                <p>Support the development of EndSol Macro</p>
            </div>

            <div className="card">
                <div className="card-header">
                    <div className="card-icon">💎</div>
                    <div>
                        <h3>Support the Project</h3>
                        <p>EndSol Macro is free and will stay free</p>
                    </div>
                </div>

                <div style={{ padding: "0 15px 15px 15px", color: "var(--text-secondary)", lineHeight: "1.6" }}>
                    <p style={{ marginBottom: "12px" }}>
                        The macro is 100% free to use. If you like it and want to support
                        further development, you can leave a donation on Boosty — one-time,
                        any amount, fully optional.
                    </p>
                    <p style={{ marginBottom: "15px" }}>
                        Donations help cover development time. Everyone who donates can ask
                        to be added to the supporters list below.
                    </p>

                    <a
                        href={BOOSTY_URL}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-accent"
                        style={{
                            width: "100%",
                            justifyContent: "center",
                            fontWeight: "bold",
                            textDecoration: "none",
                            display: "flex",
                            alignItems: "center"
                        }}
                    >
                        Donate on Boosty
                    </a>
                    <div style={{ textAlign: "center", marginTop: "8px", fontSize: "12px", opacity: 0.7 }}>
                        {BOOSTY_URL}
                    </div>
                </div>
            </div>

            <div className="card" style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: "300px" }}>
                <div className="card-header">
                    <div className="card-icon">🏆</div>
                    <div>
                        <h3>Supporters</h3>
                        <p>Thank you &lt;3</p>
                    </div>
                </div>

                <div style={{ padding: "15px", flex: 1, display: "flex", flexDirection: "column" }}>
                    <textarea
                        readOnly
                        value={donators}
                        style={{
                            flex: 1,
                            width: "100%",
                            resize: "none",
                            backgroundColor: "rgba(0,0,0,0.2)",
                            color: "var(--text-primary)",
                            border: "1px solid var(--border)",
                            padding: "12px",
                            fontFamily: "monospace",
                            fontSize: "13px",
                            lineHeight: "1.5"
                        }}
                    />
                </div>
            </div>
        </>
    );
}

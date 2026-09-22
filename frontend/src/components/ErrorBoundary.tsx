import { Component, type ReactNode, type ErrorInfo } from "react";

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("[ErrorBoundary] Caught error:", error, errorInfo);
        // Could send to logging service here
    }

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }
            return (
                <div style={{
                    padding: "40px 20px",
                    textAlign: "center",
                    color: "#ef4444",
                    background: "rgba(239, 68, 68, 0.05)",
                    border: "1px solid rgba(239, 68, 68, 0.2)",
                    borderRadius: "8px",
                    margin: "20px"
                }}>
                    <h3>⚠️ Something went wrong</h3>
                    <p style={{ color: "var(--text-secondary)", margin: "12px 0" }}>
                        An unexpected error occurred in this component.
                    </p>
                    <details style={{ textAlign: "left", maxWidth: "600px", margin: "0 auto", fontSize: "12px" }}>
                        <summary style={{ cursor: "pointer", color: "var(--text-muted)" }}>Error details</summary>
                        <pre style={{ 
                            marginTop: "8px", 
                            padding: "12px", 
                            background: "rgba(0,0,0,0.3)", 
                            borderRadius: "4px",
                            overflow: "auto",
                            whiteSpace: "pre-wrap"
                        }}>
                            {this.state.error?.message}
                            {this.state.error?.stack && `\n\n${this.state.error.stack}`}
                        </pre>
                    </details>
                    <button
                        onClick={() => window.location.reload()}
                        style={{
                            marginTop: "16px",
                            padding: "8px 20px",
                            background: "var(--primary)",
                            color: "white",
                            border: "none",
                            borderRadius: "4px",
                            cursor: "pointer",
                            fontWeight: 600
                        }}
                    >
                        Reload Page
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}

export default ErrorBoundary;
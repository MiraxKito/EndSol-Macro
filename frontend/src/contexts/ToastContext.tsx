import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
    id: number;
    message: string;
    type: ToastType;
    duration?: number;
}

interface ToastContextType {
    showToast: (message: string, type: ToastType, duration?: number) => void;
    showSuccess: (message: string, duration?: number) => void;
    showError: (message: string, duration?: number) => void;
    showWarning: (message: string, duration?: number) => void;
    showInfo: (message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const [idCounter, setIdCounter] = useState(0);

    const removeToast = useCallback((id: number) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const showToast = useCallback((message: string, type: ToastType, duration = 4000) => {
        const id = idCounter + 1;
        setIdCounter(id);
        setToasts(prev => [...prev, { id, message, type, duration }]);
        if (duration > 0) {
            setTimeout(() => removeToast(id), duration);
        }
    }, [idCounter, removeToast]);

    const showSuccess = useCallback((message: string, duration?: number) => showToast(message, "success", duration), [showToast]);
    const showError = useCallback((message: string, duration?: number) => showToast(message, "error", duration), [showToast]);
    const showWarning = useCallback((message: string, duration?: number) => showToast(message, "warning", duration), [showToast]);
    const showInfo = useCallback((message: string, duration?: number) => showToast(message, "info", duration), [showToast]);

    return (
        <ToastContext.Provider value={{ showToast, showSuccess, showError, showWarning, showInfo }}>
            {children}
            <ToastContainer toasts={toasts} onRemove={removeToast} />
        </ToastContext.Provider>
    );
}

function ToastContainer({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: number) => void }) {
    const typeStyles: Record<ToastType, { bg: string; border: string; icon: string }> = {
        success: { bg: "rgba(34, 197, 94, 0.15)", border: "rgba(34, 197, 94, 0.4)", icon: "✅" },
        error: { bg: "rgba(239, 68, 68, 0.15)", border: "rgba(239, 68, 68, 0.4)", icon: "❌" },
        warning: { bg: "rgba(245, 158, 11, 0.15)", border: "rgba(245, 158, 11, 0.4)", icon: "⚠️" },
        info: { bg: "rgba(59, 130, 246, 0.15)", border: "rgba(59, 130, 246, 0.4)", icon: "ℹ️" },
    };

    return (
        <div style={{
            position: "fixed",
            bottom: "20px",
            right: "20px",
            zIndex: 9999,
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            pointerEvents: "none",
            maxWidth: "380px"
        }}>
            {toasts.map(toast => {
                const style = typeStyles[toast.type];
                return (
                    <div
                        key={toast.id}
                        style={{
                            pointerEvents: "auto",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            padding: "12px 16px",
                            background: style.bg,
                            border: `1px solid ${style.border}`,
                            borderRadius: "8px",
                            color: "var(--text-bright)",
                            fontSize: "0.85rem",
                            fontWeight: 500,
                            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
                            animation: "slideIn 0.3s ease-out"
                        }}
                    >
                        <span style={{ fontSize: "1.1rem" }}>{style.icon}</span>
                        <span style={{ flex: 1 }}>{toast.message}</span>
                        <button
                            onClick={() => onRemove(toast.id)}
                            style={{
                                background: "transparent",
                                border: "none",
                                color: "var(--text-muted)",
                                cursor: "pointer",
                                padding: "4px",
                                fontSize: "1rem",
                                lineHeight: 1
                            }}
                        >
                            ✕
                        </button>
                    </div>
                );
            })}
        </div>
    );
}

export function useToast() {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error("useToast must be used within a ToastProvider");
    }
    return context;
}

export default ToastProvider;
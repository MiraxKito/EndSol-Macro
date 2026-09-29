import { useState } from "react";
import { useT } from "../i18n";
import "./UpdateBanner.css";

interface UpdateBannerProps {
    version: string;
    downloadUrl: string;
    updateStatus: string | null;
    onDismiss?: () => void;
    onDontAskAgain?: () => Promise<void>;
}

export default function UpdateBanner({ version, downloadUrl, updateStatus, onDismiss, onDontAskAgain }: UpdateBannerProps) {
    const t = useT();
    const [isUpdatingLocal, setIsUpdatingLocal] = useState(false);

    const handleUpdate = async () => {
        setIsUpdatingLocal(true);
        try {
            if (window.pywebview && window.pywebview.api) {
                await window.pywebview.api.apply_update(downloadUrl, version);
            }
        } catch (e) {
            setIsUpdatingLocal(false);
        }
    };

    const failed = updateStatus === "failed";
    const isDone = updateStatus?.startsWith("done|") ?? false;
    const doneFilename = isDone ? updateStatus!.split("|")[1] : "";
    const isUpdating = isUpdatingLocal || updateStatus === "downloading";

    if ((failed || isDone) && isUpdatingLocal) {
        setIsUpdatingLocal(false);
    }

    return (
        <div className={`update-banner ${failed ? "update-banner-error" : ""} ${isDone ? "update-banner-success" : ""}`}>
            <div className="update-banner-content">
                <span className="update-icon">
                    {failed ? "⚠️" : isDone ? "✅" : "❗"}
                </span>
                <span className="update-text">
                    {failed
                        ? t("Update failed. Please try downloading again.")
                        : isDone
                            ? (t("Updated!") + " " + (doneFilename || t("Restarting")))
                            : isUpdating
                                ? t("Downloading update...")
                                : `${t("New EndSol Macro version is available")}: ${version}`
                    }
                </span>
            </div>
            {!isUpdating && !isDone && (
                <div className="update-banner-actions">
                    <button className="update-btn update-btn-primary" onClick={handleUpdate}>
                        {failed ? t("Retry Update") : t("Update")}
                    </button>
                    {!failed && (
                        <button className="update-btn update-btn-secondary" onClick={onDontAskAgain}>
                            {t("Don't notify again")}
                        </button>
                    )}
                    <button className="update-banner-close" title={t("Close")} aria-label={t("Close")} onClick={onDismiss}>
                        ✕
                    </button>
                </div>
            )}
            {(isUpdating || isDone) && !failed && (
                <div className="update-banner-actions">
                    <button className="update-banner-close" title={t("Close")} aria-label={t("Close")} onClick={onDismiss}>
                        ✕
                    </button>
                </div>
            )}
            {isUpdating && !failed && !isDone && (
                <div className="update-spinner" />
            )}
        </div>
    );
}

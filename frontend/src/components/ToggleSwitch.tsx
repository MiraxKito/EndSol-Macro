import React from "react";

interface ToggleSwitchProps {
    label: string;
    description?: React.ReactNode;
    checked: boolean;
    onChange: (val: boolean) => void;
    disabled?: boolean;
}

export default function ToggleSwitch({ label, description, checked, onChange, disabled }: ToggleSwitchProps) {
    return (
        <div className="toggle-row" style={disabled ? { opacity: 0.5, pointerEvents: "none" } : {}}>
            <div className="toggle-label">
                <span className="label-text">{label}</span>
                {description && <span className="label-desc">{description}</span>}
            </div>
            <label className="toggle-switch">
                <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} disabled={disabled} />
                <span className="toggle-slider" />
            </label>
        </div>
    );
}

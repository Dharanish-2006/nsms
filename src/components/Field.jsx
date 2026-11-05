import { useId, useState } from "react";
import { icons } from "../assets";
import { AssetIcon } from "./Icon";

const EYE = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
    <path
      d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
    <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
  </svg>
);
const EYE_OFF = (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
    <path
      d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4M6.5 6.6A17 17 0 0 0 2 12s3.6 7 10 7a9.6 9.6 0 0 0 4-.9M9.9 9.9a3 3 0 0 0 4.2 4.2"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export function Field({
  label,
  value,
  onChange,
  type = "text",
  icon = icons.fieldUser,
  error,
  placeholder,
  autoComplete,
  inputMode,
  maxLength,
  disabled,
  action,
}) {
  const errorId = useId();
  const [shown, setShown] = useState(false);
  const isPassword = type === "password";
  return (
    <label className={`form-field ${error ? "has-error" : ""}`}>
      <span>{label}</span>
      <div>
        <AssetIcon src={icon} size={18} />
        <input
          type={isPassword && shown ? "text" : type}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          inputMode={inputMode}
          maxLength={maxLength}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          onChange={(e) => onChange(e.target.value)}
        />
        {isPassword ? (
          <button
            type="button"
            className="eye-button"
            aria-label={shown ? "Hide password" : "Show password"}
            aria-pressed={shown}
            onClick={() => setShown(!shown)}
          >
            {shown ? EYE_OFF : EYE}
          </button>
        ) : (
          action
        )}
      </div>
      {error && (
        <small id={errorId} role="alert">
          {error}
        </small>
      )}
    </label>
  );
}

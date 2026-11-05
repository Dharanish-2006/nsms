import { useId } from "react";
import { icons } from "../assets";
import { AssetIcon } from "./Icon";

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
  return (
    <label className={`form-field ${error ? "has-error" : ""}`}>
      <span>{label}</span>
      <div>
        <AssetIcon src={icon} size={18} />
        <input
          type={type}
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
        {action}
      </div>
      {error && (
        <small id={errorId} role="alert">
          {error}
        </small>
      )}
    </label>
  );
}

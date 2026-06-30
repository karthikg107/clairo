"use client";

/**
 * CLR-012 — Language mismatch warning.
 *
 * Shown when the backend detects a document language that differs
 * from what the user selected in CLR-014. The user can:
 *  1. Switch to the detected language (recommended)
 *  2. Keep their original selection and continue
 *
 * Non-blocking: user always has an override path.
 * WCAG 2.1 AA: role="alert", min-touch 48px, focus-visible.
 */

import { useTranslations } from "next-intl";

export interface LanguageMismatchWarningProps {
  detectedCode: string;
  detectedName: string;
  selectedCode: string;
  selectedName: string;
  /** Called when user picks the detected language. */
  onUseDetected: (code: string, name: string) => void;
  /** Called when user overrides and keeps their selection. */
  onKeepSelected: () => void;
}

export function LanguageMismatchWarning({
  detectedCode,
  detectedName,
  selectedCode,
  selectedName,
  onUseDetected,
  onKeepSelected,
}: LanguageMismatchWarningProps) {
  const t = useTranslations("language_mismatch");

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="rounded-lg border-l-4 border-warning-600 bg-warning-50 px-4 py-4"
    >
      {/* Icon + heading */}
      <div className="flex items-start gap-3 mb-3">
        <span
          className="mt-0.5 shrink-0 text-warning-700 text-lg"
          aria-hidden="true"
        >
          ⚠
        </span>
        <div>
          <h2 className="text-sm font-semibold text-warning-900 mb-1">
            {t("heading")}
          </h2>
          <p className="text-sm text-warning-800">
            {t("body", { detected: detectedName, selected: selectedName })}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2">
        {/* Primary: switch to detected */}
        <button
          type="button"
          onClick={() => onUseDetected(detectedCode, detectedName)}
          className={[
            "w-full min-h-[48px] rounded-lg bg-warning-700 px-4",
            "text-sm font-semibold text-white",
            "focus:outline-none focus:ring-2 focus:ring-warning-500 focus-visible:ring-2",
            "motion-safe:transition-colors hover:bg-warning-800",
          ].join(" ")}
        >
          {t("use_detected", { lang: detectedName })}
        </button>

        {/* Secondary: keep selection */}
        <button
          type="button"
          onClick={onKeepSelected}
          className={[
            "w-full min-h-[48px] rounded-lg border border-warning-400 bg-white px-4",
            "text-sm font-medium text-warning-800",
            "focus:outline-none focus:ring-2 focus:ring-warning-500 focus-visible:ring-2",
            "motion-safe:transition-colors hover:bg-warning-50",
          ].join(" ")}
        >
          {t("keep_selected", { lang: selectedName })}
        </button>
      </div>
    </div>
  );
}

export default LanguageMismatchWarning;

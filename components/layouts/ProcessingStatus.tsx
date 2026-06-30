"use client";

/**
 * CLR-017 — Processing status screen (SCR-07).
 *
 * Rules:
 * - Never shows blank screen or just a spinner
 * - Four sequential named steps
 * - Smooth indeterminate progress bar
 * - Privacy reminder always visible
 * - Cancel button with confirmation dialog
 * - Extra encouragement at 45s
 * - Timeout at 90s → error screen, document confirmed deleted
 * - prefers-reduced-motion: progress animates at 0 speed
 * - WCAG 2.1 AA: aria-live regions, focus management
 */

import { useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";

// ── Step definitions ──────────────────────────────────────────────────────────

export type StepId = "reading" | "identifying" | "generating" | "finishing";

const STEPS: { id: StepId; icon: string }[] = [
  { id: "reading",     icon: "📄" },
  { id: "identifying", icon: "🔍" },
  { id: "generating",  icon: "✍️" },
  { id: "finishing",   icon: "✅" },
];

export type ProcessingState =
  | { status: "processing"; currentStep: StepId }
  | { status: "timeout" }
  | { status: "cancelled" };

// ── Props ─────────────────────────────────────────────────────────────────────

export interface ProcessingStatusProps {
  docLanguage: string;       // BCP-47
  outputLanguage: string;    // BCP-47
  docLanguageName: string;
  outputLanguageName: string;
  /** Externally-driven current step (from WebSocket / poll). */
  currentStep?: StepId;
  onCancel: () => void;
  onTimeout: () => void;
  /** Override elapsed seconds for testing. */
  _elapsedOverride?: number;
}

// ── Step indicator ────────────────────────────────────────────────────────────

function StepRow({
  icon,
  label,
  state,
}: {
  icon: string;
  label: string;
  state: "done" | "active" | "pending";
}) {
  return (
    <li
      className={[
        "flex items-center gap-3 py-2.5",
        state === "active" ? "opacity-100" : state === "done" ? "opacity-100" : "opacity-40",
      ].join(" ")}
      aria-current={state === "active" ? "step" : undefined}
    >
      <span
        className={[
          "flex items-center justify-center w-8 h-8 rounded-full text-base shrink-0",
          state === "done"
            ? "bg-success-100 text-success-700"
            : state === "active"
            ? "bg-brand-100 text-brand-700 animate-pulse motion-reduce:animate-none"
            : "bg-dark-100 text-dark-400",
        ].join(" ")}
        aria-hidden="true"
      >
        {state === "done" ? "✓" : icon}
      </span>
      <span
        className={[
          "text-sm font-medium",
          state === "active" ? "text-brand-700" : state === "done" ? "text-success-700" : "text-dark-400",
        ].join(" ")}
      >
        {label}
      </span>
      {state === "active" && (
        <span className="ml-auto">
          <span
            className="inline-flex gap-0.5"
            aria-hidden="true"
          >
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1 h-1 rounded-full bg-brand-500 animate-bounce motion-reduce:animate-none"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </span>
        </span>
      )}
    </li>
  );
}

// ── Indeterminate progress bar ────────────────────────────────────────────────

function ProgressBar({ elapsed, timeout }: { elapsed: number; timeout: number }) {
  // Never reaches 100% (indeterminate feel) but moves forward meaningfully
  const pct = Math.min(90, (elapsed / timeout) * 100 + 5);
  return (
    <div
      role="progressbar"
      aria-label="Analysis progress"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      className="h-1.5 w-full bg-dark-100 rounded-full overflow-hidden"
    >
      <div
        className="h-full bg-brand-500 rounded-full motion-safe:transition-all motion-safe:duration-1000"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ── Cancel dialog ─────────────────────────────────────────────────────────────

function CancelDialog({
  onConfirm,
  onClose,
  t,
}: {
  onConfirm: () => void;
  onClose: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  const id = useId();
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { confirmRef.current?.focus(); }, []);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={id}
      className="fixed inset-0 z-50 flex items-center justify-center bg-dark-900/60 px-4"
    >
      <div className="w-full max-w-sm bg-white rounded-2xl p-6 space-y-4">
        <h2 id={id} className="text-base font-semibold text-dark-900">
          {t("cancel_dialog.heading")}
        </h2>
        <p className="text-sm text-dark-600">{t("cancel_dialog.body")}</p>
        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 min-h-[48px] rounded-xl border border-dark-300 text-sm font-medium text-dark-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {t("cancel_dialog.keep_going")}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={onConfirm}
            className="flex-1 min-h-[48px] rounded-xl bg-danger-600 text-sm font-semibold text-white focus:outline-none focus:ring-2 focus:ring-danger-500"
          >
            {t("cancel_dialog.confirm_cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const TIMEOUT_SECONDS   = 90;
const ENCOURAGE_SECONDS = 45;
const TICK_MS           = 1000;

export function ProcessingStatus({
  docLanguageName,
  outputLanguageName,
  currentStep = "reading",
  onCancel,
  onTimeout,
  _elapsedOverride,
}: ProcessingStatusProps) {
  const t = useTranslations("processing");
  const [elapsed, setElapsed] = useState(_elapsedOverride ?? 0);
  const [showCancel, setShowCancel] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (_elapsedOverride !== undefined) return; // controlled in tests
    intervalRef.current = setInterval(() => {
      setElapsed((s) => s + 1);
    }, TICK_MS);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [_elapsedOverride]);

  // Timeout at 90s
  useEffect(() => {
    if (elapsed >= TIMEOUT_SECONDS && !timedOut) {
      setTimedOut(true);
      if (intervalRef.current) clearInterval(intervalRef.current);
      onTimeout();
    }
  }, [elapsed, timedOut, onTimeout]);

  const stepIndex = STEPS.findIndex((s) => s.id === currentStep);
  const showEncouragement = elapsed >= ENCOURAGE_SECONDS && !timedOut;

  return (
    <>
      <div className="flex flex-col min-h-screen bg-background px-4 pt-8 pb-8">
        {/* Language pair header */}
        <div className="flex items-center justify-center gap-2 mb-8 text-sm text-dark-600">
          <span className="font-medium text-dark-900">{docLanguageName}</span>
          <span aria-hidden="true">→</span>
          <span className="font-medium text-dark-900">{outputLanguageName}</span>
        </div>

        {/* Progress bar */}
        <ProgressBar elapsed={elapsed} timeout={TIMEOUT_SECONDS} />

        {/* Time estimate */}
        <p className="text-xs text-dark-400 text-center mt-2 mb-6" aria-live="polite">
          {showEncouragement
            ? t("encouragement")
            : t("estimate")}
        </p>

        {/* Steps */}
        <ol
          className="space-y-0 mb-8"
          aria-label={t("steps_label")}
        >
          {STEPS.map((step, i) => {
            const state =
              i < stepIndex ? "done" : i === stepIndex ? "active" : "pending";
            return (
              <StepRow
                key={step.id}
                icon={step.icon}
                label={t(`steps.${step.id}`)}
                state={state}
              />
            );
          })}
        </ol>

        {/* Privacy reminder — always visible */}
        <div
          className="flex items-start gap-2 bg-brand-50 border border-brand-200 rounded-xl px-4 py-3 mb-auto"
          aria-label={t("privacy_label")}
        >
          <span aria-hidden="true" className="text-brand-600 mt-0.5 shrink-0">🔒</span>
          <p className="text-xs text-brand-800 leading-relaxed">{t("privacy")}</p>
        </div>

        {/* Cancel */}
        <button
          type="button"
          onClick={() => setShowCancel(true)}
          className={[
            "mt-6 w-full min-h-[48px] rounded-xl border border-dark-300 bg-white",
            "text-sm font-medium text-dark-600",
            "focus:outline-none focus:ring-2 focus:ring-brand-500 focus-visible:ring-2",
          ].join(" ")}
        >
          {t("cancel")}
        </button>
      </div>

      {showCancel && (
        <CancelDialog
          t={t}
          onConfirm={onCancel}
          onClose={() => setShowCancel(false)}
        />
      )}
    </>
  );
}

export default ProcessingStatus;

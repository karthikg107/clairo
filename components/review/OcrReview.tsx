"use client";

/**
 * CLR-011 — OCR Pre-Analysis Review Screen
 *
 * DESIGN RULES (non-negotiable):
 * - Legal disclaimer always visible, never dismissable
 * - Mandatory checkbox — "Continue" disabled until checked
 * - No "Skip" button — screen cannot be bypassed
 * - Confidence colour-coding: HIGH=normal, MEDIUM=warning, LOW=danger, NUMBER=accent
 * - Inline word editing: tap word → input replaces it → confirm with Enter/blur
 * - Mobile-first at 375px
 * - WCAG 2.1 AA: min-touch-target 48px, focus-visible, prefers-reduced-motion
 * - RTL support via dir prop
 */

import React, {
  useCallback,
  useId,
  useRef,
  useState,
} from "react";
import { useTranslations } from "next-intl";

// ── Types (mirror backend OcrResponse shape) ────────────────────────────────

export type ConfidenceLevel = "high" | "medium" | "low" | "number";

export interface OcrWordData {
  text: string;
  confidence: number;
  confidence_level: ConfidenceLevel;
  bounding_box?: Record<string, number> | null;
}

export interface OcrPageData {
  page_number: number;
  words: OcrWordData[];
  low_confidence_ratio: number;
}

export interface OcrResultData {
  pages: OcrPageData[];
  total_pages: number;
  source: "gcv" | "textract" | "direct";
  skip_review: boolean;
}

export interface OcrReviewProps {
  result: OcrResultData;
  filename: string;
  onConfirm: (correctedPages: OcrPageData[]) => void;
  onCancel: () => void;
  dir?: "ltr" | "rtl";
}

// ── Confidence colour tokens ─────────────────────────────────────────────────

const LEVEL_CLASSES: Record<ConfidenceLevel, string> = {
  high: "",                                          // no highlight
  medium: "bg-warning-100 text-warning-900 rounded", // amber
  low: "bg-danger-100 text-danger-900 rounded",      // red
  number: "bg-accent-100 text-accent-900 rounded",   // orange — always verify
};

const LEVEL_RING: Record<ConfidenceLevel, string> = {
  high: "focus:ring-brand-500",
  medium: "focus:ring-warning-500",
  low: "focus:ring-danger-500",
  number: "focus:ring-accent-500",
};

// ── Single editable word ─────────────────────────────────────────────────────

interface WordTokenProps {
  word: OcrWordData;
  onChange: (next: string) => void;
}

function WordToken({ word, onChange }: WordTokenProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(word.text);
  const inputRef = useRef<HTMLInputElement>(null);
  const id = useId();

  const open = () => {
    setDraft(word.text);
    setEditing(true);
    // focus after render
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const commit = () => {
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed && trimmed !== word.text) {
      onChange(trimmed);
    }
  };

  const classes = LEVEL_CLASSES[word.confidence_level];
  const ringClass = LEVEL_RING[word.confidence_level];

  if (editing) {
    return (
      <input
        ref={inputRef}
        id={id}
        className={[
          "inline-block px-1 py-0.5 text-sm border border-brand-500 rounded",
          "focus:outline-none focus:ring-2",
          ringClass,
          "min-w-[3rem] max-w-[16rem]",
          // no motion for reduced-motion users — just show the field
        ].join(" ")}
        style={{ width: `${Math.max(draft.length + 2, 4)}ch` }}
        value={draft}
        aria-label={`Edit word: ${word.text}`}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); commit(); }
          if (e.key === "Escape") { setEditing(false); }
        }}
      />
    );
  }

  return (
    <button
      type="button"
      onClick={open}
      className={[
        "inline text-sm px-0.5 py-0 leading-relaxed cursor-pointer",
        "focus:outline-none focus:ring-2 focus-visible:ring-2",
        ringClass,
        classes,
        "motion-safe:transition-colors",
        // min-touch but as inline — we rely on the surrounding line-height
        "select-text",
      ].join(" ")}
      aria-label={`Word: ${word.text}. Confidence: ${word.confidence_level}. Tap to edit.`}
      title={`Confidence: ${Math.round(word.confidence * 100)}%`}
    >
      {word.text}
    </button>
  );
}

// ── Confidence legend ────────────────────────────────────────────────────────

function ConfidenceLegend({ t }: { t: ReturnType<typeof useTranslations> }) {
  const items: { level: ConfidenceLevel; key: string }[] = [
    { level: "high",   key: "legend.high" },
    { level: "medium", key: "legend.medium" },
    { level: "low",    key: "legend.low" },
    { level: "number", key: "legend.number" },
  ];
  return (
    <div
      className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-dark-700 mb-4"
      role="list"
      aria-label={t("legend.label")}
    >
      {items.map(({ level, key }) => (
        <span key={level} role="listitem" className="flex items-center gap-1">
          <span
            className={["inline-block w-3 h-3 rounded-sm border border-dark-200", LEVEL_CLASSES[level] || "bg-dark-100"].join(" ")}
            aria-hidden
          />
          {t(key)}
        </span>
      ))}
    </div>
  );
}

// ── Page section ─────────────────────────────────────────────────────────────

interface PageSectionProps {
  page: OcrPageData;
  onWordChange: (wordIdx: number, next: string) => void;
  t: ReturnType<typeof useTranslations>;
}

function PageSection({ page, onWordChange, t }: PageSectionProps) {
  const lowPct = Math.round(page.low_confidence_ratio * 100);
  return (
    <section aria-label={t("page_label", { n: page.page_number })}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-dark-900">
          {t("page_label", { n: page.page_number })}
        </h3>
        {lowPct > 0 && (
          <span
            className="text-xs text-danger-700 font-medium"
            aria-live="polite"
          >
            {t("low_confidence_pct", { pct: lowPct })}
          </span>
        )}
      </div>

      {/* Inline flowing text */}
      <div
        className={[
          "bg-white border border-dark-200 rounded-lg p-4 leading-loose",
          "text-sm text-dark-900 break-words",
        ].join(" ")}
        role="region"
        aria-label={t("text_region_label", { n: page.page_number })}
      >
        {page.words.map((w, i) => (
          <React.Fragment key={i}>
            <WordToken
              word={w}
              onChange={(next) => onWordChange(i, next)}
            />
            {" "}
          </React.Fragment>
        ))}
        {page.words.length === 0 && (
          <p className="text-dark-500 italic">{t("empty_page")}</p>
        )}
      </div>
    </section>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export function OcrReview({
  result,
  filename,
  onConfirm,
  onCancel,
  dir = "ltr",
}: OcrReviewProps) {
  const t = useTranslations("review");
  const td = useTranslations("disclaimer");

  // Deep-copy pages so edits don't mutate the prop
  const [pages, setPages] = useState<OcrPageData[]>(
    () => result.pages.map((p) => ({
      ...p,
      words: p.words.map((w) => ({ ...w })),
    }))
  );
  const [confirmed, setConfirmed] = useState(false);
  const checkboxId = useId();
  const headingId = useId();

  const handleWordChange = useCallback(
    (pageIdx: number, wordIdx: number, next: string) => {
      setPages((prev) =>
        prev.map((p, pi) =>
          pi !== pageIdx
            ? p
            : {
                ...p,
                words: p.words.map((w, wi) =>
                  wi !== wordIdx ? w : { ...w, text: next }
                ),
              }
        )
      );
    },
    []
  );

  const handleConfirm = () => {
    if (!confirmed) return;
    onConfirm(pages);
  };

  const totalLowWords = pages.reduce(
    (acc, p) => acc + p.words.filter((w) => w.confidence_level === "low").length,
    0
  );
  const totalNumberWords = pages.reduce(
    (acc, p) => acc + p.words.filter((w) => w.confidence_level === "number").length,
    0
  );

  return (
    <div
      className="flex flex-col min-h-screen bg-background"
      dir={dir}
    >
      {/* ── Non-dismissable legal disclaimer ── */}
      <div
        role="note"
        aria-label={td("label")}
        className="sticky top-0 z-10 bg-warning-50 border-b border-warning-300 px-4 py-3"
      >
        <p className="text-xs text-warning-900 font-medium leading-snug">
          {td("review")}
        </p>
      </div>

      {/* ── Scrollable body ── */}
      <main
        className="flex-1 overflow-y-auto px-4 pt-4 pb-36"
        id="review-body"
        aria-labelledby={headingId}
      >
        {/* Header */}
        <h1
          id={headingId}
          className="text-xl font-bold text-dark-900 mb-1"
        >
          {t("heading")}
        </h1>
        <p className="text-sm text-dark-600 mb-4">
          {t("subheading", { filename })}
        </p>

        {/* Summary warnings */}
        {(totalLowWords > 0 || totalNumberWords > 0) && (
          <div
            className="bg-danger-50 border border-danger-200 rounded-lg px-4 py-3 mb-4 space-y-1"
            role="alert"
          >
            {totalLowWords > 0 && (
              <p className="text-sm text-danger-800">
                {t("warning.low_words", { count: totalLowWords })}
              </p>
            )}
            {totalNumberWords > 0 && (
              <p className="text-sm text-danger-800">
                {t("warning.number_words", { count: totalNumberWords })}
              </p>
            )}
          </div>
        )}

        {/* Legend */}
        <ConfidenceLegend t={t} />

        {/* Pages */}
        <div className="space-y-6">
          {pages.map((page, pi) => (
            <PageSection
              key={page.page_number}
              page={page}
              onWordChange={(wi, next) => handleWordChange(pi, wi, next)}
              t={t}
            />
          ))}
        </div>

        {/* Source badge */}
        <p className="mt-4 text-xs text-dark-400">
          {t("source", { source: result.source })}
        </p>
      </main>

      {/* ── Fixed bottom bar ── */}
      <div
        className={[
          "fixed bottom-0 inset-x-0 z-20 bg-white border-t border-dark-200",
          "px-4 py-4 space-y-3",
          // safe area for notched phones
          "pb-[calc(1rem+env(safe-area-inset-bottom))]",
        ].join(" ")}
      >
        {/* Mandatory confirmation checkbox */}
        <label
          htmlFor={checkboxId}
          className="flex items-start gap-3 cursor-pointer"
        >
          <input
            id={checkboxId}
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            className={[
              "mt-0.5 h-5 w-5 shrink-0 rounded border-dark-400",
              "text-brand-600 focus:ring-2 focus:ring-brand-500 focus-visible:ring-2",
              "cursor-pointer",
            ].join(" ")}
            aria-describedby="confirm-hint"
          />
          <span className="text-sm text-dark-800 leading-snug">
            {t("confirm_label")}
          </span>
        </label>
        <p id="confirm-hint" className="text-xs text-dark-500 sr-only">
          {t("confirm_hint")}
        </p>

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            className={[
              "flex-1 min-h-[48px] rounded-lg border border-dark-300",
              "text-sm font-medium text-dark-700 bg-white",
              "focus:outline-none focus:ring-2 focus:ring-brand-500 focus-visible:ring-2",
              "motion-safe:transition-colors hover:bg-dark-50",
            ].join(" ")}
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!confirmed}
            aria-disabled={!confirmed}
            className={[
              "flex-[2] min-h-[48px] rounded-lg",
              "text-sm font-semibold text-white",
              confirmed
                ? "bg-brand-600 hover:bg-brand-700 motion-safe:transition-colors"
                : "bg-dark-300 cursor-not-allowed",
              "focus:outline-none focus:ring-2 focus:ring-brand-500 focus-visible:ring-2",
            ].join(" ")}
          >
            {t("continue")}
          </button>
        </div>
      </div>
    </div>
  );
}

export default OcrReview;

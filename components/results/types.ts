/**
 * CLR-018 — Shared types for the analysis results screen.
 * Mirrors the schema enforced by backend/app/services/analysis.py (_validate_schema).
 */

export type FlagLevel = 'none' | 'note' | 'review'

export interface ClauseNumber {
  value: string
  context: string
}

export interface Clause {
  id: string
  title: string
  original_text: string
  explanation: string
  frequency_pct: number | null
  is_protective: boolean
  flag_level: FlagLevel
  numbers: ClauseNumber[]
}

export interface AnalysisResult {
  document_type: string
  summary: string
  clauses: Clause[]
  protective_clause_count: number
  review_clause_count: number
}

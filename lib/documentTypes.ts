/**
 * CLR-023 — Document type -> icon mapping for the dashboard history list.
 * Mirrors backend/app/services/document_type.py's PERMITTED_TYPES.
 */
import {
  Home,
  Briefcase,
  FileSignature,
  FileText,
  File,
  type LucideIcon,
} from 'lucide-react'

export type PermittedDocumentType =
  'rental' | 'employment' | 'freelance' | 'tos' | 'other_permitted'

export const DOCUMENT_TYPE_ICONS: Record<PermittedDocumentType, LucideIcon> = {
  rental: Home,
  employment: Briefcase,
  freelance: FileSignature,
  tos: FileText,
  other_permitted: File,
}

export function getDocumentTypeIcon(documentType: string): LucideIcon {
  return DOCUMENT_TYPE_ICONS[documentType as PermittedDocumentType] ?? File
}

/** Filter chip values shown on the dashboard — "other" groups tos + other_permitted. */
export type FilterChip = 'all' | 'rental' | 'employment' | 'freelance' | 'other'

export const FILTER_CHIPS: FilterChip[] = [
  'all',
  'rental',
  'employment',
  'freelance',
  'other',
]

export function matchesFilter(documentType: string, filter: FilterChip): boolean {
  if (filter === 'all') return true
  if (filter === 'other')
    return documentType === 'tos' || documentType === 'other_permitted'
  return documentType === filter
}

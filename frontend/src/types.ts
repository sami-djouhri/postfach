export interface User {
  id: number;
  username: string;
  display_name: string;
  created_at: string;
}

export interface Tag {
  id: number;
  name: string;
  color: string;
}

export interface LetterFile {
  id: number;
  filename: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  page_number: number;
  ocr_text: string | null;
  created_at: string;
}

export interface Letter {
  id: number;
  title: string;
  sender: string | null;
  category: string | null;
  received_date: string | null;
  letter_date: string | null;
  ocr_text: string | null;
  ocr_status: string;
  analysis_status: string;
  llm_summary: string | null;
  notes: string | null;
  is_archived: boolean;
  snoozed_until: string | null;
  paperless_id: string | null;
  created_at: string;
  updated_at: string;
  files: LetterFile[];
  tags: Tag[];
}

export interface LetterListItem {
  id: number;
  title: string;
  sender: string | null;
  category: string | null;
  received_date: string | null;
  ocr_status: string;
  analysis_status: string;
  is_archived: boolean;
  snoozed_until: string | null;
  paperless_id: string | null;
  created_at: string;
  file_count: number;
  tags: Tag[];
}

export interface LlmResult {
  absender: string | null;
  kategorie: string | null;
  zusammenfassung: string | null;
  fristen: Array<{
    typ: string;
    datum: string;
    beschreibung: string;
  }>;
  calendar_synced: number;
  calendar_skipped: number;
  calendar_errors: string[];
  error: string | null;
}

export interface Stats {
  total_letters: number;
  archived_letters: number;
  pending_ocr: number;
  categories: Record<string, number>;
  recent_letters: LetterListItem[];
}

export const CATEGORIES = [
  'Rechnung',
  'Vertrag',
  'Behoerde',
  'Versicherung',
  'Bank',
  'Gesundheit',
  'Sonstiges',
] as const;

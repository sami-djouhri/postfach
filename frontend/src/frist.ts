// Anzeige von Fristen. Rechnet nichts, was der Server schon rechnet (tage,
// ueberfaellig), ausser fuer die Karte, die nur das Datum kennt.

export function datumDe(iso: string | null | undefined): string {
  if (!iso) return '';
  const [j, m, t] = iso.slice(0, 10).split('-');
  if (!j || !m || !t) return iso;
  return `${t}.${m}.${j}`;
}

export function heuteIso(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const t = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${t}`;
}

// Ganze Tage von heute bis zum Datum, lokal gerechnet (ohne Zeitzonenversatz).
export function tageBis(iso: string): number {
  const [j, m, t] = iso.slice(0, 10).split('-').map(Number);
  const ziel = Date.UTC(j, m - 1, t);
  const h = new Date();
  const heute = Date.UTC(h.getFullYear(), h.getMonth(), h.getDate());
  return Math.round((ziel - heute) / 86400000);
}

export function fristText(tage: number): string {
  if (tage < -1) return `seit ${-tage} Tagen überfällig`;
  if (tage === -1) return 'seit gestern überfällig';
  if (tage === 0) return 'heute fällig';
  if (tage === 1) return 'morgen fällig';
  return `in ${tage} Tagen`;
}

// Zustand fuer die Farbe: ueberfaellig rot, in einer Woche gold, sonst ruhig.
export function fristStufe(tage: number): 'ueberfaellig' | 'bald' | 'spaeter' {
  if (tage < 0) return 'ueberfaellig';
  if (tage <= 7) return 'bald';
  return 'spaeter';
}

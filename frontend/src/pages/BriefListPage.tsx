import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Facetten, FacetteWert, LetterListItem } from '../types';
import LetterCard from '../components/LetterCard';

// Suche und Ordner ohne eigene Tabelle: Absender, Kategorie, Tag und Jahr
// kommen aus den vorhandenen Daten (/letters/facetten), dazu Volltext (FTS5).
// Jeder Filter steht in der Adresse, damit ein Zurueck, ein Neuladen oder ein
// Lesezeichen dieselbe Liste zeigt.

type Bereich = 'kategorie' | 'absender' | 'tag' | 'jahr' | 'status';

const BEREICHE: Array<{ id: Bereich; name: string }> = [
  { id: 'kategorie', name: 'Kategorie' },
  { id: 'absender', name: 'Absender' },
  { id: 'tag', name: 'Tag' },
  { id: 'jahr', name: 'Jahr' },
  { id: 'status', name: 'Status' },
];

const STATUS: FacetteWert[] = [
  { wert: 'offen', name: 'Offen', anzahl: -1 },
  { wert: 'erledigt', name: 'Erledigt', anzahl: -1 },
];

export default function BriefListPage() {
  const [params, setParams] = useSearchParams();
  const [letters, setLetters] = useState<LetterListItem[]>([]);
  const [facetten, setFacetten] = useState<Facetten | null>(null);
  const [loading, setLoading] = useState(true);
  const [offenerBereich, setOffenerBereich] = useState<Bereich | null>(null);

  const q = params.get('q') || '';
  const kategorie = params.get('kategorie') || params.get('category') || '';
  const absender = params.get('absender') || '';
  const tags = (params.get('tag') || '').split(',').filter(Boolean);
  const jahr = params.get('jahr') || '';
  const status = params.get('status') || '';
  const archiv = params.get('archiv') === '1';
  const wiedervorlage = params.get('wv') === '1';
  const bedeutung = params.get('modus') === 'bedeutung';

  const [eingabe, setEingabe] = useState(q);
  useEffect(() => { setEingabe(q); }, [q]);

  // Ein Filter aendern, die uebrigen behalten. replace, damit nicht jeder
  // Klick einen Eintrag im Verlauf hinterlaesst.
  const setze = (aenderung: Record<string, string | null>) => {
    const neu = new URLSearchParams(params);
    neu.delete('category');
    for (const [k, v] of Object.entries(aenderung)) {
      if (v) neu.set(k, v); else neu.delete(k);
    }
    setParams(neu, { replace: true });
  };

  useEffect(() => {
    api.get<Facetten>('/letters/facetten').then(setFacetten).catch(() => setFacetten(null));
  }, []);

  useEffect(() => {
    setLoading(true);
    let endpoint: string;
    if (q && bedeutung) {
      endpoint = `/letters/semantic-search?q=${encodeURIComponent(q)}&limit=30`;
    } else {
      const p = new URLSearchParams({ limit: '200' });
      if (q) p.set('q', q);
      if (kategorie) p.set('category', kategorie);
      if (absender) p.set('correspondent_id', absender);
      if (tags.length) p.set('tag_ids_all', tags.join(','));
      if (jahr) p.set('jahr', jahr);
      if (status) p.set('status', status);
      if (archiv) p.set('is_archived', 'true');
      if (wiedervorlage) p.set('include_snoozed', 'true');
      endpoint = `/letters?${p}`;
    }
    let aktuell = true;
    api.get<LetterListItem[]>(endpoint)
      .then((l) => { if (aktuell) setLetters(l); })
      .catch(() => { if (aktuell) setLetters([]); })
      .finally(() => { if (aktuell) setLoading(false); });
    return () => { aktuell = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const werte = (b: Bereich): FacetteWert[] => {
    if (b === 'status') return STATUS;
    if (!facetten) return [];
    return { kategorie: facetten.kategorien, absender: facetten.absender, tag: facetten.tags, jahr: facetten.jahre }[b];
  };

  const name = (b: Bereich, wert: string) => werte(b).find((w) => w.wert === wert)?.name || wert;

  const istGewaehlt = (b: Bereich, wert: string) => {
    if (b === 'kategorie') return kategorie === wert;
    if (b === 'absender') return absender === wert;
    if (b === 'tag') return tags.includes(wert);
    if (b === 'jahr') return jahr === wert;
    return status === wert;
  };

  const waehle = (b: Bereich, wert: string) => {
    if (b === 'tag') {
      const neu = tags.includes(wert) ? tags.filter((t) => t !== wert) : [...tags, wert];
      setze({ tag: neu.join(',') || null });
      return;
    }
    setze({ [b]: istGewaehlt(b, wert) ? null : wert });
    setOffenerBereich(null);
  };

  const aktive = useMemo(() => {
    const a: Array<{ key: string; text: string; weg: () => void }> = [];
    if (q) a.push({ key: 'q', text: `„${q}“`, weg: () => setze({ q: null }) });
    if (kategorie) a.push({ key: 'k', text: kategorie, weg: () => setze({ kategorie: null }) });
    if (absender) a.push({ key: 'a', text: name('absender', absender), weg: () => setze({ absender: null }) });
    for (const t of tags) a.push({ key: `t${t}`, text: `#${name('tag', t)}`, weg: () => waehle('tag', t) });
    if (jahr) a.push({ key: 'j', text: jahr, weg: () => setze({ jahr: null }) });
    if (status) a.push({ key: 's', text: name('status', status), weg: () => setze({ status: null }) });
    if (archiv) a.push({ key: 'ar', text: 'Archiviert', weg: () => setze({ archiv: null }) });
    if (wiedervorlage) a.push({ key: 'wv', text: 'mit Wiedervorlage', weg: () => setze({ wv: null }) });
    return a;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, facetten]);

  const suchen = (e: FormEvent) => {
    e.preventDefault();
    setze({ q: eingabe.trim() || null });
  };

  const bereichAktiv = (b: Bereich) =>
    ({ kategorie: !!kategorie, absender: !!absender, tag: tags.length > 0, jahr: !!jahr, status: !!status }[b]);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Briefe</h1>
        <Link to="/papierkorb" className="btn btn-ghost btn-sm">Papierkorb</Link>
      </div>

      <form className="search-bar" onSubmit={suchen} role="search">
        <input
          type="search"
          value={eingabe}
          onChange={(e) => {
            setEingabe(e.target.value);
            if (!e.target.value) setze({ q: null });
          }}
          placeholder={bedeutung ? 'Nach Bedeutung suchen, z.B. Kündigung Handy' : 'Volltext: Absender, Inhalt, Notizen'}
          className="search-input"
          aria-label="Briefe durchsuchen"
          enterKeyHint="search"
        />
      </form>

      <div className="chip-reihe" role="toolbar" aria-label="Filter">
        {BEREICHE.map((b) => (
          <button
            key={b.id}
            type="button"
            className={`chip ${bereichAktiv(b.id) ? 'gewaehlt' : ''} ${offenerBereich === b.id ? 'offen' : ''}`}
            aria-expanded={offenerBereich === b.id}
            onClick={() => setOffenerBereich(offenerBereich === b.id ? null : b.id)}
          >
            {b.name}
          </button>
        ))}
        <button
          type="button"
          className={`chip ${bedeutung ? 'active' : ''}`}
          aria-pressed={bedeutung}
          title="Statt nach Wörtern nach ähnlichem Inhalt suchen"
          onClick={() => setze({ modus: bedeutung ? null : 'bedeutung' })}
        >
          Nach Bedeutung
        </button>
      </div>

      {offenerBereich && (
        <div className="chip-auswahl">
          {werte(offenerBereich).length === 0 ? (
            <span className="text-muted text-sm">Nichts zum Filtern vorhanden.</span>
          ) : (
            werte(offenerBereich).map((w) => (
              <button
                key={w.wert}
                type="button"
                className={`chip ${istGewaehlt(offenerBereich, w.wert) ? 'active' : ''}`}
                aria-pressed={istGewaehlt(offenerBereich, w.wert)}
                onClick={() => waehle(offenerBereich, w.wert)}
              >
                {offenerBereich === 'tag' && w.color && <span className="chip-punkt" style={{ background: w.color }} />}
                {w.name}
                {w.anzahl >= 0 && <span className="chip-zahl">{w.anzahl}</span>}
              </button>
            ))
          )}
          {offenerBereich === 'status' && (
            <>
              <button type="button" className={`chip ${archiv ? 'active' : ''}`} aria-pressed={archiv}
                onClick={() => setze({ archiv: archiv ? null : '1' })}>
                Archiviert
              </button>
              <button type="button" className={`chip ${wiedervorlage ? 'active' : ''}`} aria-pressed={wiedervorlage}
                onClick={() => setze({ wv: wiedervorlage ? null : '1' })}>
                Mit Wiedervorlage
              </button>
            </>
          )}
        </div>
      )}

      {aktive.length > 0 && (
        <div className="chip-aktiv" aria-label="Aktive Filter">
          {aktive.map((a) => (
            <button key={a.key} type="button" className="chip active" onClick={a.weg} aria-label={`Filter ${a.text} entfernen`}>
              {a.text} <span aria-hidden="true">×</span>
            </button>
          ))}
          {aktive.length > 1 && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setParams({}, { replace: true })}>
              Alle entfernen
            </button>
          )}
        </div>
      )}

      {bedeutung && q && aktive.length > 1 && (
        <p className="text-muted text-sm">Die Suche nach Bedeutung beachtet die übrigen Filter nicht.</p>
      )}

      {loading ? (
        <p className="text-muted">Laden...</p>
      ) : letters.length === 0 ? (
        <p className="text-muted">Keine Briefe gefunden.</p>
      ) : (
        <>
          <p className="text-muted text-sm treffer-zahl">
            {letters.length} {letters.length === 1 ? 'Brief' : 'Briefe'}
          </p>
          <div className="letter-list">
            {letters.map((l) => <LetterCard key={l.id} letter={l} />)}
          </div>
        </>
      )}
    </div>
  );
}

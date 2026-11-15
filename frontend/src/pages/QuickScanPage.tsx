import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { quickScanMulti } from '../api';

// Handy: Foto rein, fertig.
//
// Ein Foto ist eine Seite, "Speichern" schickt den Brief ab. Hochgeladen wird
// im Hintergrund, nacheinander (der Dienst erkennt den Text beim Hochladen,
// mehrere gleichzeitig wuerden sich nur gegenseitig bremsen). Die Seite ist
// sofort frei fuer den naechsten Brief. Alle Knoepfe liegen unten, unter dem
// Daumen, damit es mit einer Hand geht.

type Stand = 'wartet' | 'laeuft' | 'fertig' | 'fehler';

interface Sendung {
  nr: number;
  seiten: File[];
  stand: Stand;
  letterId?: number;
  fehler?: string;
}

interface Seite {
  datei: File;
  vorschau: string; // leer bei PDF
}

export default function QuickScanPage() {
  const kameraRef = useRef<HTMLInputElement>(null);
  const dateiRef = useRef<HTMLInputElement>(null);
  const naechsteNr = useRef(1);

  const [seiten, setSeiten] = useState<Seite[]>([]);
  const [sendungen, setSendungen] = useState<Sendung[]>([]);

  const offen = sendungen.some((s) => s.stand === 'wartet' || s.stand === 'laeuft');

  // Eine Sendung nach der anderen. Die Sperre liegt in einer Ref und nicht nur
  // im Zustand: der wird erst beim naechsten Zeichnen sichtbar, und ein zweiter
  // Effektlauf dazwischen haette denselben Brief zweimal geschickt.
  const laeuft = useRef(false);
  useEffect(() => {
    if (laeuft.current) return;
    const naechste = sendungen.find((s) => s.stand === 'wartet');
    if (!naechste) return;
    laeuft.current = true;
    const setze = (teil: Partial<Sendung>) =>
      setSendungen((alle) => alle.map((s) => (s.nr === naechste.nr ? { ...s, ...teil } : s)));
    setze({ stand: 'laeuft', fehler: undefined });
    quickScanMulti(naechste.seiten)
      .then((brief) => setze({ stand: 'fertig', letterId: brief.id }))
      .catch((e: Error) => setze({ stand: 'fehler', fehler: e.message || 'Hochladen fehlgeschlagen' }))
      .finally(() => {
        laeuft.current = false;
        // Den Effekt fuer die naechste wartende Sendung anstossen.
        setSendungen((alle) => [...alle]);
      });
  }, [sendungen]);

  // Wer die Seite verlaesst, solange noch etwas hochlaedt, verliert es.
  useEffect(() => {
    if (!offen) return;
    const warnen = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', warnen);
    return () => window.removeEventListener('beforeunload', warnen);
  }, [offen]);

  // Vorschauen freigeben, wenn die Seite geht.
  const seitenRef = useRef(seiten);
  seitenRef.current = seiten;
  useEffect(() => () => seitenRef.current.forEach((s) => s.vorschau && URL.revokeObjectURL(s.vorschau)), []);

  const hinzu = (liste: FileList | null) => {
    if (!liste) return;
    const neu = Array.from(liste)
      .filter((f) => f.type.startsWith('image/') || f.type === 'application/pdf')
      .map((f) => ({ datei: f, vorschau: f.type.startsWith('image/') ? URL.createObjectURL(f) : '' }));
    if (neu.length) setSeiten((s) => [...s, ...neu]);
  };

  const entferne = (i: number) => {
    setSeiten((s) => {
      if (s[i]?.vorschau) URL.revokeObjectURL(s[i].vorschau);
      return s.filter((_, idx) => idx !== i);
    });
  };

  const speichern = () => {
    if (!seiten.length) return;
    const nr = naechsteNr.current++;
    setSendungen((alle) => [{ nr, seiten: seiten.map((s) => s.datei), stand: 'wartet' }, ...alle]);
    seiten.forEach((s) => s.vorschau && URL.revokeObjectURL(s.vorschau));
    setSeiten([]);
  };

  const nochmal = (nr: number) =>
    setSendungen((alle) => alle.map((s) => (s.nr === nr ? { ...s, stand: 'wartet' } : s)));

  const n = seiten.length;

  return (
    <div className="page scan-page">
      <h1>Scannen</h1>
      <p className="text-muted scan-hinweis">
        Ein Foto je Seite. Speichern schickt den Brief ab, Texterkennung und Einordnung laufen
        danach von selbst.
      </p>

      {n > 0 && (
        <div className="quick-scan-pages" aria-label="Seiten dieses Briefes">
          {seiten.map((s, i) => (
            <div key={s.vorschau || `${s.datei.name}-${i}`} className="quick-scan-thumb">
              <span className="badge">Seite {i + 1}</span>
              {s.vorschau ? (
                <img src={s.vorschau} alt={`Seite ${i + 1}`} />
              ) : (
                <div className="quick-scan-pdf">{s.datei.name}</div>
              )}
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => entferne(i)}
                aria-label={`Seite ${i + 1} entfernen`}
              >
                Entfernen
              </button>
            </div>
          ))}
        </div>
      )}

      {sendungen.length > 0 && (
        <section className="scan-sendungen" aria-live="polite">
          <h2>Gesendet</h2>
          <ul>
            {sendungen.map((s) => (
              <li key={s.nr} className={`scan-sendung scan-${s.stand}`}>
                <span className="scan-sendung-name">
                  Brief {s.nr} <span className="akte">{s.seiten.length} {s.seiten.length === 1 ? 'Seite' : 'Seiten'}</span>
                </span>
                {s.stand === 'wartet' && <span className="text-muted">wartet</span>}
                {s.stand === 'laeuft' && <span className="text-muted">wird hochgeladen</span>}
                {s.stand === 'fertig' && s.letterId && (
                  <Link to={`/briefe/${s.letterId}`} className="btn btn-ghost btn-sm">Gespeichert, ansehen</Link>
                )}
                {s.stand === 'fehler' && (
                  <>
                    <span className="error-text">{s.fehler}</span>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => nochmal(s.nr)}>
                      Nochmal
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <input
        ref={kameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => { hinzu(e.target.files); e.target.value = ''; }}
      />
      <input
        ref={dateiRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.pdf"
        multiple
        hidden
        onChange={(e) => { hinzu(e.target.files); e.target.value = ''; }}
      />

      {/* Daumenleiste: klebt unten ueber der Navigation. */}
      <div className="scan-leiste">
        {n === 0 ? (
          <>
            <button type="button" className="btn btn-primary btn-lg btn-full" onClick={() => kameraRef.current?.click()}>
              {sendungen.length ? 'Nächsten Brief fotografieren' : 'Brief fotografieren'}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => dateiRef.current?.click()}>
              Aus Dateien wählen
            </button>
          </>
        ) : (
          <div className="scan-leiste-zeile">
            <button type="button" className="btn btn-secondary btn-lg" onClick={() => kameraRef.current?.click()}>
              + Seite
            </button>
            <button type="button" className="btn btn-primary btn-lg scan-speichern" onClick={speichern}>
              Speichern ({n} {n === 1 ? 'Seite' : 'Seiten'})
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

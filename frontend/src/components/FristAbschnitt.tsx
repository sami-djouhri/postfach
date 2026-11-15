import { useEffect, useState } from 'react';
import { api } from '../api';
import { FristVorschlag, Letter } from '../types';
import { datumDe, fristStufe, fristText, tageBis } from '../frist';

interface Props {
  letter: Letter;
  onGeaendert: () => void;
}

// Frist und Erledigt am einzelnen Brief. Eine im Text erkannte Frist steht
// als Vorschlag da und wird erst mit "Übernehmen" gesetzt.
export default function FristAbschnitt({ letter, onGeaendert }: Props) {
  const [datum, setDatum] = useState(letter.frist_bis || '');
  const [vorschlag, setVorschlag] = useState<FristVorschlag | null>(null);
  const [fehler, setFehler] = useState('');
  const [beschaeftigt, setBeschaeftigt] = useState(false);

  useEffect(() => { setDatum(letter.frist_bis || ''); }, [letter.frist_bis]);

  useEffect(() => {
    setVorschlag(null);
    if (letter.frist_bis || letter.erledigt_am || !letter.ocr_text) return;
    api.get<FristVorschlag | null>(`/letters/${letter.id}/frist-vorschlag`)
      .then(setVorschlag)
      .catch(() => setVorschlag(null));
  }, [letter.id, letter.frist_bis, letter.erledigt_am, letter.ocr_text]);

  const tun = async (f: () => Promise<unknown>) => {
    setBeschaeftigt(true);
    setFehler('');
    try {
      await f();
      onGeaendert();
    } catch (e: any) {
      setFehler(e.message);
    } finally {
      setBeschaeftigt(false);
    }
  };

  const setzeFrist = (wert: string | null) => tun(() => api.put(`/letters/${letter.id}`, { frist_bis: wert }));
  const geaendert = (datum || null) !== (letter.frist_bis || null);

  return (
    <section className="detail-section" aria-labelledby="frist-titel">
      <div className="section-header">
        <h2 id="frist-titel">Frist</h2>
        {letter.erledigt_am ? (
          <button className="btn btn-secondary btn-sm" disabled={beschaeftigt}
            onClick={() => tun(() => api.del(`/letters/${letter.id}/erledigt`))}>
            Wieder öffnen
          </button>
        ) : (
          <button className="btn btn-primary btn-sm" disabled={beschaeftigt}
            onClick={() => tun(() => api.post(`/letters/${letter.id}/erledigt`))}>
            Erledigt
          </button>
        )}
      </div>

      {letter.erledigt_am && (
        <p className="frist-hinweis">
          <span className="frist-marke frist-erledigt">erledigt</span>{' '}
          am {datumDe(letter.erledigt_am)}
        </p>
      )}

      <div className="frist-feld">
        <label htmlFor="frist-datum" className="text-muted text-sm">Zu erledigen bis</label>
        <input id="frist-datum" type="date" value={datum} onChange={(e) => setDatum(e.target.value)} />
        {geaendert && (
          <button className="btn btn-primary btn-sm" disabled={beschaeftigt} onClick={() => setzeFrist(datum || null)}>
            Speichern
          </button>
        )}
        {letter.frist_bis && !geaendert && (
          <button className="btn btn-ghost btn-sm" disabled={beschaeftigt} onClick={() => setzeFrist(null)}>
            Frist entfernen
          </button>
        )}
      </div>

      {letter.frist_bis && !letter.erledigt_am && (
        <p className={`frist-hinweis frist-${fristStufe(tageBis(letter.frist_bis))}`}>
          <span className="frist-stand">{fristText(tageBis(letter.frist_bis))}</span>
        </p>
      )}

      {vorschlag && (
        <div className="frist-vorschlag-box">
          <p>
            Im Brief steht eine Frist: <strong>{datumDe(vorschlag.datum)}</strong>
            <br />
            <span className="text-muted">„{vorschlag.stelle}“</span>
          </p>
          <button className="btn btn-primary btn-sm" disabled={beschaeftigt} onClick={() => setzeFrist(vorschlag.datum)}>
            Übernehmen
          </button>
        </div>
      )}

      {fehler && <p className="error-text">{fehler}</p>}
    </section>
  );
}

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { Fristen } from '../types';
import { datumDe, fristStufe, fristText } from '../frist';

// Oben in der Uebersicht: offene Fristen, die frueheste zuerst, ueberfaellige
// rot. Darunter, was im Text eines Briefes nach Frist aussieht und noch nicht
// bestaetigt ist. Ein Vorschlag wird erst mit "Übernehmen" zur Frist.
export default function FristenBlock() {
  const navigate = useNavigate();
  const [daten, setDaten] = useState<Fristen | null>(null);
  const [fehler, setFehler] = useState('');
  const [beschaeftigt, setBeschaeftigt] = useState<number | null>(null);

  const laden = () =>
    api.get<Fristen>('/letters/fristen').then(setDaten).catch((e) => setFehler(e.message));

  useEffect(() => { laden(); }, []);

  const aktion = async (id: number, tun: () => Promise<unknown>) => {
    setBeschaeftigt(id);
    try {
      await tun();
      await laden();
    } catch (e: any) {
      setFehler(e.message);
    } finally {
      setBeschaeftigt(null);
    }
  };

  if (fehler) return <p className="error-text">{fehler}</p>;
  if (!daten) return null;
  const { offen, vorschlaege } = daten;
  const ueberfaellig = offen.filter((f) => f.ueberfaellig).length;

  return (
    <section className="fristen" aria-labelledby="fristen-titel">
      <div className="section-header">
        <h2 id="fristen-titel">Fristen</h2>
        {ueberfaellig > 0 && <span className="fristen-zaehler">{ueberfaellig} überfällig</span>}
      </div>

      {offen.length === 0 ? (
        <p className="text-muted fristen-leer">Keine offenen Fristen.</p>
      ) : (
        <ul className="frist-liste">
          {offen.map((f) => (
            <li key={f.id} className={`frist-zeile frist-${fristStufe(f.tage)}`}>
              <button className="frist-inhalt" onClick={() => navigate(`/briefe/${f.id}`)}>
                <span className="frist-datum akte">{datumDe(f.frist_bis)}</span>
                <span className="frist-titel">{f.title}</span>
                <span className="frist-unter">
                  {f.sender ? `${f.sender} · ` : ''}<span className="frist-stand">{fristText(f.tage)}</span>
                </span>
              </button>
              <button
                className="btn btn-secondary btn-sm"
                disabled={beschaeftigt === f.id}
                onClick={() => aktion(f.id, () => api.post(`/letters/${f.id}/erledigt`))}
              >
                Erledigt
              </button>
            </li>
          ))}
        </ul>
      )}

      {vorschlaege.length > 0 && (
        <>
          <h3 className="fristen-unterkopf">Frist erkannt, bitte prüfen</h3>
          <ul className="frist-liste">
            {vorschlaege.map((v) => (
              <li key={v.id} className="frist-zeile frist-vorschlag">
                <button className="frist-inhalt" onClick={() => navigate(`/briefe/${v.id}`)}>
                  <span className="frist-datum akte">{datumDe(v.vorschlag.datum)}</span>
                  <span className="frist-titel">{v.title}</span>
                  <span className="frist-unter frist-stelle">„{v.vorschlag.stelle}“</span>
                </button>
                <div className="frist-knoepfe">
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={beschaeftigt === v.id}
                    onClick={() => aktion(v.id, () => api.put(`/letters/${v.id}`, { frist_bis: v.vorschlag.datum }))}
                  >
                    Übernehmen
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    title="Brief abhaken, ohne Frist"
                    disabled={beschaeftigt === v.id}
                    onClick={() => aktion(v.id, () => api.post(`/letters/${v.id}/erledigt`))}
                  >
                    Nichts zu tun
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/* Der Eingangsstempel: das Kennzeichen dieses Dienstes.
 *
 * Er traegt zwei Angaben in einem Zeichen, und beide braucht man, um mit
 * einem Archiv zu arbeiten:
 *
 *   WANN kam der Brief an, und
 *   IST SEIN TEXT ERKANNT, also: findet man ihn in zwei Jahren wieder.
 *
 * Das zweite stand vorher als "ok", "...", "!" oder "-" in der Ecke der
 * Karte. Wer den Code nicht kennt, liest daraus nichts, und gerade dieser
 * Zustand entscheidet ueber die Brauchbarkeit des ganzen Archivs: ein Brief
 * ohne erkannten Text ist ein Bild in einem Stapel.
 *
 * Die Unterscheidung liegt in der FORM, nicht in der Farbe:
 *   durchgezogener Rahmen  = Text erkannt, der Brief ist auffindbar
 *   gestrichelter Rahmen   = laeuft gerade, noch nicht fertig
 *   Rahmen mit Querstrich  = fehlgeschlagen, der Brief ist nur ein Bild
 *   blasser Rahmen         = noch nicht begonnen
 */

interface Props {
  /** Eingangsdatum, wie es vom Server kommt (ISO oder bereits formatiert). */
  datum?: string | null;
  /** done | processing | error | pending */
  ocr?: string | null;
}

const ERKLAERUNG: Record<string, string> = {
  done: 'Text erkannt, der Brief ist durchsuchbar',
  processing: 'Text wird gerade erkannt',
  error: 'Texterkennung fehlgeschlagen, der Brief ist nur ein Bild',
  pending: 'Texterkennung steht noch aus',
};

/* Ein Poststempel traegt Tag und Monat gross, das Jahr klein. */
function stempeldatum(roh: string | null | undefined): { zeile1: string; zeile2: string } | null {
  if (!roh) return null;
  const d = new Date(roh);
  if (Number.isNaN(d.getTime())) {
    // Kommt schon formatiert herein: unveraendert zeigen statt zu raten.
    return { zeile1: roh, zeile2: '' };
  }
  const tag = String(d.getDate()).padStart(2, '0');
  const monat = String(d.getMonth() + 1).padStart(2, '0');
  return { zeile1: `${tag}.${monat}.`, zeile2: String(d.getFullYear()) };
}

export default function Eingangsstempel({ datum, ocr }: Props) {
  const stand = ocr ?? 'pending';
  const d = stempeldatum(datum);
  const titel = ERKLAERUNG[stand] ?? ERKLAERUNG.pending;

  return (
    <div
      className={`stempel stempel-${stand}`}
      title={datum ? `Eingang ${datum}. ${titel}` : titel}
      aria-label={datum ? `Eingegangen am ${datum}. ${titel}` : titel}
    >
      <span className="stempel-kopf">Eingang</span>
      {d ? (
        <>
          <span className="stempel-tag">{d.zeile1}</span>
          {d.zeile2 && <span className="stempel-jahr">{d.zeile2}</span>}
        </>
      ) : (
        <span className="stempel-tag stempel-ohne">ohne</span>
      )}
    </div>
  );
}

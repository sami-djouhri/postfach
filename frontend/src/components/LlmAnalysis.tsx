import { useState } from 'react';
import { api } from '../api';
import { LlmResult } from '../types';

interface Props {
  letterId: number;
  hasOcrText: boolean;
  currentSummary: string | null;
  onApply: (data: { sender?: string; category?: string; llm_summary?: string }) => void;
}

export default function LlmAnalysis({ letterId, hasOcrText, currentSummary, onApply }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<LlmResult | null>(null);
  const [error, setError] = useState('');

  const analyze = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const r = await api.post<LlmResult>(`/letters/${letterId}/analyze`);
      if (r.error) {
        setError(r.error);
      } else {
        setResult(r);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (!hasOcrText) {
    return (
      <div className="llm-section">
        <p className="text-muted">Bitte zuerst OCR ausfuehren, bevor die KI-Analyse gestartet werden kann.</p>
      </div>
    );
  }

  return (
    <div className="llm-section">
      <div className="llm-header">
        <h3>KI-Analyse</h3>
        <button className="btn btn-secondary" onClick={analyze} disabled={loading}>
          {loading ? 'Analysiere...' : 'KI-Analyse starten'}
        </button>
      </div>

      {error && <p className="error-text">{error}</p>}

      {currentSummary && !result && (
        <div className="llm-result">
          <label>Gespeicherte Zusammenfassung:</label>
          <p>{currentSummary}</p>
        </div>
      )}

      {result && (
        <div className="llm-result">
          {result.absender && (
            <div className="llm-field">
              <label>Absender-Vorschlag:</label>
              <span>{result.absender}</span>
            </div>
          )}
          {result.kategorie && (
            <div className="llm-field">
              <label>Kategorie-Vorschlag:</label>
              <span>{result.kategorie}</span>
            </div>
          )}
          {result.zusammenfassung && (
            <div className="llm-field">
              <label>Zusammenfassung:</label>
              <p>{result.zusammenfassung}</p>
            </div>
          )}
          {result.fristen?.length > 0 && (
            <div className="llm-field">
              <label>Fristen und Termine:</label>
              <ul className="deadline-list">
                {result.fristen.map((frist, index) => (
                  <li key={`${frist.typ}-${frist.datum}-${index}`}>
                    <strong>{frist.datum}</strong> {frist.beschreibung}
                    <span className="text-muted"> ({frist.typ})</span>
                  </li>
                ))}
              </ul>
              <p className="text-muted">
                Kalender: {result.calendar_synced} synchronisiert
                {result.calendar_skipped ? `, ${result.calendar_skipped} uebersprungen` : ''}
              </p>
              {result.calendar_errors?.map((msg, index) => (
                <p key={index} className="error-text">{msg}</p>
              ))}
            </div>
          )}
          <button
            className="btn btn-primary"
            onClick={() => onApply({
              sender: result.absender || undefined,
              category: result.kategorie || undefined,
              llm_summary: result.zusammenfassung || undefined,
            })}
          >
            Vorschlaege uebernehmen
          </button>
        </div>
      )}
    </div>
  );
}

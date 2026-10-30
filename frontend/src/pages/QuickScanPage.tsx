import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { quickScanMulti } from '../api';

// Mobile-First Scan-Flow: Foto(s) machen → quick-scan-multi → Letter angelegt mit OCR
// LLM-Analyse läuft im Hintergrund, Felder erscheinen wenn man die Detail-Seite öffnet.
export default function QuickScanPage() {
  const navigate = useNavigate();
  const cameraRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [pages, setPages] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const accepted = Array.from(list).filter(
      (f) => f.type.startsWith('image/') || f.type === 'application/pdf'
    );
    if (!accepted.length) return;
    setPages((p) => [...p, ...accepted]);
    setPreviews((p) => [
      ...p,
      ...accepted.map((f) => (f.type.startsWith('image/') ? URL.createObjectURL(f) : '')),
    ]);
  };

  const removePage = (i: number) => {
    setPages(pages.filter((_, idx) => idx !== i));
    setPreviews(previews.filter((_, idx) => idx !== i));
  };

  const submit = async () => {
    if (!pages.length) {
      setError('Mindestens eine Seite hinzufügen');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const letter = await quickScanMulti(pages, title.trim() || undefined);
      // Aufräumen (object-URLs)
      previews.forEach((u) => u && URL.revokeObjectURL(u));
      navigate(`/briefe/${letter.id}`);
    } catch (e: any) {
      setError(e.message || 'Fehler beim Hochladen');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <h1>Schnell scannen</h1>
      <p className="text-muted">
        Mach Fotos vom Brief. Der Service richtet sie automatisch gerade und erkennt Absender,
        Kategorie und Zusammenfassung.
      </p>

      <div className="form-group">
        <label htmlFor="qs-title">Titel (optional)</label>
        <input
          id="qs-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={`Brief vom ${new Date().toISOString().split('T')[0]}`}
        />
      </div>

      <div className="quick-scan-pages">
        {previews.map((src, i) => (
          <div key={i} className="quick-scan-thumb">
            <span className="badge">Seite {i + 1}</span>
            {src ? (
              <img src={src} alt={`Seite ${i + 1}`} />
            ) : (
              <div className="quick-scan-pdf">{pages[i].name}</div>
            )}
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => removePage(i)} disabled={loading}>
              Entfernen
            </button>
          </div>
        ))}
      </div>

      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        style={{ display: 'none' }}
        onChange={(e) => {
          addFiles(e.target.files);
          e.target.value = '';
        }}
      />
      <input
        ref={fileRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.pdf"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => {
          addFiles(e.target.files);
          e.target.value = '';
        }}
      />

      <div className="quick-scan-actions">
        <button
          type="button"
          className="btn btn-primary btn-full"
          onClick={() => cameraRef.current?.click()}
          disabled={loading}
        >
          {pages.length === 0 ? 'Foto aufnehmen' : 'Weitere Seite aufnehmen'}
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-full"
          onClick={() => fileRef.current?.click()}
          disabled={loading}
        >
          Aus Galerie/Dateien wählen
        </button>
      </div>

      {error && <p className="error-text">{error}</p>}

      <button
        type="button"
        className="btn btn-primary btn-full"
        style={{ marginTop: '1rem' }}
        onClick={submit}
        disabled={loading || !pages.length}
      >
        {loading
          ? 'Wird verarbeitet...'
          : `Brief speichern (${pages.length} ${pages.length === 1 ? 'Seite' : 'Seiten'})`}
      </button>
      {loading && (
        <p className="text-muted text-sm">
          OCR läuft jetzt, KI-Analyse läuft im Hintergrund (~1-2 Min). Du kannst die Detailseite
          öffnen und in Kürze aktualisieren.
        </p>
      )}
    </div>
  );
}

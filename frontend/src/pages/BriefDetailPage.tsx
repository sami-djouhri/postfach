import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, apiUrl, uploadFile } from '../api';
import { Letter, Tag, CATEGORIES } from '../types';
import CategoryBadge from '../components/CategoryBadge';
import TagChip from '../components/TagChip';
import FileUpload from '../components/FileUpload';
import LlmAnalysis from '../components/LlmAnalysis';

export default function BriefDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [letter, setLetter] = useState<Letter | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ title: '', sender: '', category: '', received_date: '', letter_date: '', notes: '' });
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [snoozeInput, setSnoozeInput] = useState('');
  const [forwarding, setForwarding] = useState(false);

  const load = () => {
    api.get<Letter>(`/letters/${id}`).then(l => {
      setLetter(l);
      setForm({
        title: l.title,
        sender: l.sender || '',
        category: l.category || '',
        received_date: l.received_date || '',
        letter_date: l.letter_date || '',
        notes: l.notes || '',
      });
      setSelectedTagIds(l.tags.map(t => t.id));
    }).catch(e => setError(e.message));

    api.get<Tag[]>('/tags').then(setTags).catch(() => {});
  };

  useEffect(() => { load(); }, [id]);

  // Auto-Refresh wenn Pipeline läuft (OCR/Analyse): alle 3s bis fertig.
  useEffect(() => {
    if (!letter) return;
    const busy = letter.ocr_status === 'processing' || letter.ocr_status === 'pending'
      || letter.analysis_status === 'processing';
    if (!busy) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [letter?.ocr_status, letter?.analysis_status]);

  const save = async () => {
    try {
      await api.put(`/letters/${id}`, {
        ...form,
        sender: form.sender || null,
        category: form.category || null,
        received_date: form.received_date || null,
        letter_date: form.letter_date || null,
        notes: form.notes || null,
        tag_ids: selectedTagIds,
      });
      setEditing(false);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const runOcr = async () => {
    setOcrLoading(true);
    try {
      await api.post(`/letters/${id}/ocr`);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setOcrLoading(false);
    }
  };

  const handleUpload = async (files: File[]) => {
    setUploading(true);
    try {
      for (const f of files) {
        await uploadFile(Number(id), f);
      }
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Brief wirklich loeschen?')) return;
    await api.del(`/letters/${id}`);
    navigate('/briefe');
  };

  const handleDeleteFile = async (fileId: number) => {
    if (!confirm('Datei wirklich loeschen?')) return;
    await api.del(`/letters/${id}/files/${fileId}`);
    load();
  };

  const applyLlm = async (data: { sender?: string; category?: string; llm_summary?: string }) => {
    await api.put(`/letters/${id}`, data);
    load();
  };

  const toggleArchive = async () => {
    await api.put(`/letters/${id}`, { is_archived: !letter?.is_archived });
    load();
  };

  const setSnooze = async (isoDate: string | null) => {
    try {
      await api.put(`/letters/${id}`, { snoozed_until: isoDate });
      setSnoozeInput('');
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const snoozePreset = (days: number) => {
    const d = new Date();
    d.setDate(d.getDate() + days);
    d.setHours(9, 0, 0, 0);
    setSnooze(d.toISOString());
  };

  const snoozeFromInput = () => {
    if (!snoozeInput) return;
    setSnooze(new Date(snoozeInput).toISOString());
  };

  const forwardPaperless = async () => {
    if (forwarding) return;
    if (!confirm('Brief an Paperless weiterleiten?')) return;
    setForwarding(true);
    try {
      await api.post(`/letters/${id}/forward-to-paperless`, {
        tag_ids: letter?.tags.map(t => t.id) || [],
        summary: letter?.llm_summary || undefined,
      });
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setForwarding(false);
    }
  };

  if (error && !letter) return <div className="page"><p className="error-text">{error}</p></div>;
  if (!letter) return <div className="page"><p>Laden...</p></div>;

  return (
    <div className="page">
      <div className="page-header">
        <button className="btn btn-ghost" onClick={() => navigate('/briefe')}>&larr; Zurueck</button>
        <div className="header-actions">
          <a
            href={apiUrl(`/letters/${id}/pdf`)}
            className="btn btn-secondary"
            download
          >
            PDF
          </a>
          <button className="btn btn-secondary" onClick={toggleArchive}>
            {letter.is_archived ? 'Wiederherstellen' : 'Archivieren'}
          </button>
          <button className="btn btn-danger" onClick={handleDelete}>Loeschen</button>
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      {/* Pipeline-Status: sichtbar wenn etwas läuft */}
      {(letter.ocr_status === 'processing' || letter.ocr_status === 'pending' || letter.analysis_status === 'processing') && (
        <div className="detail-section" style={{display:'flex', gap:'1rem', alignItems:'center'}}>
          {letter.ocr_status !== 'done' && (
            <span className="badge" title="OCR läuft im Hintergrund">
              📄 OCR: {letter.ocr_status === 'processing' ? 'läuft…' : letter.ocr_status === 'pending' ? 'wartet' : letter.ocr_status}
            </span>
          )}
          {letter.analysis_status === 'processing' && (
            <span className="badge" title="KI-Analyse läuft im Hintergrund">🧠 KI-Analyse läuft…</span>
          )}
          <span className="text-muted" style={{fontSize:'0.85em'}}>aktualisiert sich automatisch</span>
        </div>
      )}

      {/* Metadata */}
      <section className="detail-section">
        <div className="detail-header">
          <h1>{letter.title}</h1>
          {!editing && (
            <button className="btn btn-ghost" onClick={() => setEditing(true)}>Bearbeiten</button>
          )}
        </div>

        {editing ? (
          <div className="edit-form">
            <div className="form-group">
              <label>Titel</label>
              <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Absender</label>
              <input value={form.sender} onChange={e => setForm({ ...form, sender: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Kategorie</label>
              <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                <option value="">Keine</option>
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Empfangsdatum</label>
                <input type="date" value={form.received_date} onChange={e => setForm({ ...form, received_date: e.target.value })} />
              </div>
              <div className="form-group">
                <label>Briefdatum</label>
                <input type="date" value={form.letter_date} onChange={e => setForm({ ...form, letter_date: e.target.value })} />
              </div>
            </div>
            <div className="form-group">
              <label>Notizen</label>
              <textarea rows={3} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Tags</label>
              <div className="tag-select">
                {tags.map(t => (
                  <label key={t.id} className="tag-option">
                    <input
                      type="checkbox"
                      checked={selectedTagIds.includes(t.id)}
                      onChange={e => {
                        if (e.target.checked) {
                          setSelectedTagIds([...selectedTagIds, t.id]);
                        } else {
                          setSelectedTagIds(selectedTagIds.filter(id => id !== t.id));
                        }
                      }}
                    />
                    <TagChip tag={t} />
                  </label>
                ))}
              </div>
            </div>
            <div className="form-actions">
              <button className="btn btn-primary" onClick={save}>Speichern</button>
              <button className="btn btn-ghost" onClick={() => setEditing(false)}>Abbrechen</button>
            </div>
          </div>
        ) : (
          <div className="detail-meta">
            {letter.sender && <p><strong>Absender:</strong> {letter.sender}</p>}
            <CategoryBadge category={letter.category} />
            {letter.received_date && <p><strong>Empfangen:</strong> {letter.received_date}</p>}
            {letter.letter_date && <p><strong>Briefdatum:</strong> {letter.letter_date}</p>}
            {letter.notes && <p><strong>Notizen:</strong> {letter.notes}</p>}
            {letter.tags.length > 0 && (
              <div className="detail-tags">
                {letter.tags.map(t => <TagChip key={t.id} tag={t} />)}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Snooze + Paperless-Forward (Saganta Phase 2) */}
      <section className="detail-section">
        <div className="section-header">
          <h2>Wiedervorlage</h2>
        </div>
        {letter.snoozed_until ? (
          <div className="detail-meta">
            <p>
              <strong>Snoozed bis:</strong> {new Date(letter.snoozed_until).toLocaleString('de-DE')}
            </p>
            <button className="btn btn-ghost btn-sm" onClick={() => setSnooze(null)}>
              Snooze aufheben
            </button>
          </div>
        ) : (
          <div className="form-row">
            <button className="btn btn-secondary" onClick={() => snoozePreset(1)}>+1 Tag</button>
            <button className="btn btn-secondary" onClick={() => snoozePreset(7)}>+1 Woche</button>
            <button className="btn btn-secondary" onClick={() => snoozePreset(30)}>+1 Monat</button>
            <input
              type="datetime-local"
              value={snoozeInput}
              onChange={e => setSnoozeInput(e.target.value)}
            />
            <button className="btn btn-primary" onClick={snoozeFromInput} disabled={!snoozeInput}>
              Snooze
            </button>
          </div>
        )}
      </section>

      <section className="detail-section">
        <div className="section-header">
          <h2>Paperless-Archiv</h2>
          <button
            className="btn btn-secondary"
            onClick={forwardPaperless}
            disabled={forwarding || !!letter.paperless_id || letter.files.length === 0}
          >
            {letter.paperless_id ? 'Bereits weitergeleitet' : forwarding ? 'Sende...' : 'An Paperless senden'}
          </button>
        </div>
        {letter.paperless_id && (
          <p className="text-muted">Paperless-Task: <code>{letter.paperless_id}</code></p>
        )}
        {!letter.paperless_id && letter.files.length === 0 && (
          <p className="text-muted">Erst eine Datei anhängen, dann Forward möglich.</p>
        )}
      </section>

      {/* Files */}
      <section className="detail-section">
        <h2>Scans / Dateien</h2>
        {letter.files.length > 0 && (
          <div className="file-grid">
            {letter.files.map(f => (
              <div key={f.id} className="file-card">
                {f.content_type.startsWith('image/') ? (
                  <img
                    src={apiUrl(`/letters/${id}/files/${f.id}`)}
                    alt={f.original_filename}
                    className="file-preview"
                  />
                ) : (
                  <div className="file-preview file-preview-pdf">PDF</div>
                )}
                <div className="file-info">
                  <span className="file-name">{f.original_filename}</span>
                  <span className="file-size">{(f.file_size / 1024).toFixed(0)} KB</span>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => handleDeleteFile(f.id)}>
                  Loeschen
                </button>
              </div>
            ))}
          </div>
        )}
        <FileUpload onFilesSelected={handleUpload} disabled={uploading} />
        {uploading && <p className="text-muted">Hochladen...</p>}
      </section>

      {/* OCR */}
      <section className="detail-section">
        <div className="section-header">
          <h2>OCR-Texterkennung</h2>
          <button
            className="btn btn-secondary"
            onClick={runOcr}
            disabled={ocrLoading || letter.files.length === 0}
          >
            {ocrLoading ? 'Verarbeite...' : letter.ocr_status === 'done' ? 'Erneut ausfuehren' : 'OCR starten'}
          </button>
        </div>
        <p className="text-muted">
          Status: {letter.ocr_status === 'done' ? 'Abgeschlossen' :
            letter.ocr_status === 'processing' ? 'In Bearbeitung...' :
            letter.ocr_status === 'error' ? 'Fehler' : 'Ausstehend'}
        </p>
        {letter.ocr_text && (
          <pre className="ocr-text">{letter.ocr_text}</pre>
        )}
      </section>

      {/* LLM Analysis */}
      <section className="detail-section">
        <LlmAnalysis
          letterId={letter.id}
          hasOcrText={!!letter.ocr_text}
          currentSummary={letter.llm_summary}
          onApply={applyLlm}
        />
      </section>
    </div>
  );
}

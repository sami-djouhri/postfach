import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, uploadFile } from '../api';
import { Tag, CATEGORIES } from '../types';
import FileUpload from '../components/FileUpload';
import TagChip from '../components/TagChip';

export default function UploadPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [sender, setSender] = useState('');
  const [category, setCategory] = useState('');
  const [receivedDate, setReceivedDate] = useState(new Date().toISOString().split('T')[0]);
  const [letterDate, setLetterDate] = useState('');
  const [notes, setNotes] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get<Tag[]>('/tags').then(setTags).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Titel ist erforderlich');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const letter = await api.post<{ id: number }>('/letters', {
        title: title.trim(),
        sender: sender || null,
        category: category || null,
        received_date: receivedDate || null,
        letter_date: letterDate || null,
        notes: notes || null,
        tag_ids: selectedTagIds,
      });

      for (const f of files) {
        await uploadFile(letter.id, f);
      }

      navigate(`/briefe/${letter.id}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <div className="page">
      <h1>Brief erfassen</h1>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="title">Titel *</label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="z.B. Stromrechnung Maerz 2026"
            required
            autoFocus
          />
        </div>

        <div className="form-group">
          <label htmlFor="sender">Absender</label>
          <input
            id="sender"
            type="text"
            value={sender}
            onChange={(e) => setSender(e.target.value)}
            placeholder="z.B. Stadtwerke"
          />
        </div>

        <div className="form-group">
          <label htmlFor="category">Kategorie</label>
          <select id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Keine Kategorie</option>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="receivedDate">Empfangsdatum</label>
            <input
              id="receivedDate"
              type="date"
              value={receivedDate}
              onChange={(e) => setReceivedDate(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label htmlFor="letterDate">Briefdatum</label>
            <input
              id="letterDate"
              type="date"
              value={letterDate}
              onChange={(e) => setLetterDate(e.target.value)}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="notes">Notizen</label>
          <textarea
            id="notes"
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optionale Notizen..."
          />
        </div>

        {tags.length > 0 && (
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
        )}

        <div className="form-group">
          <label>Scans / Dateien</label>
          <FileUpload onFilesSelected={(newFiles) => setFiles([...files, ...newFiles])} />
          {files.length > 0 && (
            <div className="file-list-preview">
              {files.map((f, i) => (
                <div key={i} className="file-list-item">
                  <span>{f.name}</span>
                  <span className="text-muted">{(f.size / 1024).toFixed(0)} KB</span>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => removeFile(i)}>
                    Entfernen
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {error && <p className="error-text">{error}</p>}

        <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
          {loading ? 'Wird gespeichert...' : 'Brief speichern'}
        </button>
      </form>
    </div>
  );
}

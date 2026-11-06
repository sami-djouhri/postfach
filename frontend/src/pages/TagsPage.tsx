import { useEffect, useState } from 'react';
import { api } from '../api';
import { Tag } from '../types';
import TagChip from '../components/TagChip';

const PRESET_COLORS = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#6b7280', '#06b6d4'];

export default function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [name, setName] = useState('');
  const [color, setColor] = useState('#6366f1');
  const [error, setError] = useState('');

  const load = () => {
    api.get<Tag[]>('/tags').then(setTags).catch(() => {});
  };

  useEffect(() => { load(); }, []);

  const createTag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError('');
    try {
      await api.post('/tags', { name: name.trim(), color });
      setName('');
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const deleteTag = async (id: number) => {
    if (!confirm('Tag wirklich loeschen?')) return;
    await api.del(`/tags/${id}`);
    load();
  };

  return (
    <div className="page">
      <h1>Tags verwalten</h1>

      <form className="tag-form" onSubmit={createTag}>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Neuer Tag..."
          className="tag-input"
        />
        <div className="color-picker">
          {PRESET_COLORS.map(c => (
            <button
              key={c}
              type="button"
              className={`color-dot ${color === c ? 'active' : ''}`}
              style={{ backgroundColor: c }}
              onClick={() => setColor(c)}
            />
          ))}
        </div>
        <button type="submit" className="btn btn-primary" disabled={!name.trim()}>
          Erstellen
        </button>
      </form>

      {error && <p className="error-text">{error}</p>}

      <div className="tag-list">
        {tags.length === 0 ? (
          <p className="text-muted">Noch keine Tags erstellt.</p>
        ) : (
          tags.map(t => (
            <div key={t.id} className="tag-list-item">
              <TagChip tag={t} />
              <button className="btn btn-ghost btn-sm" onClick={() => deleteTag(t.id)}>
                Loeschen
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

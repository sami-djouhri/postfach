import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { LetterListItem } from '../types';

export default function PapierkorbPage() {
  const [letters, setLetters] = useState<LetterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    api.get<LetterListItem[]>('/letters?show_deleted=true&include_snoozed=true&limit=200')
      .then(setLetters)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const restore = async (id: number) => {
    try {
      await api.post(`/letters/${id}/restore`);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const hardDelete = async (id: number) => {
    if (!confirm('Endgültig löschen? Diese Aktion ist nicht umkehrbar.')) return;
    try {
      await api.del(`/letters/${id}?hard=true`);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="page">
      <h1>Papierkorb</h1>
      {error && <p className="error-text">{error}</p>}
      {loading ? (
        <p>Laden…</p>
      ) : letters.length === 0 ? (
        <p className="text-muted">Papierkorb ist leer.</p>
      ) : (
        <div className="letter-list">
          {letters.map(l => (
            <div key={l.id} className="letter-card flex justify-between items-center gap-4">
              <div>
                <Link to={`/briefe/${l.id}`}><strong>{l.title}</strong></Link>
                {l.sender && <span className="text-muted"> · {l.sender}</span>}
                {l.category && <span className="text-muted"> · {l.category}</span>}
              </div>
              <div className="flex gap-2">
                <button className="btn btn-secondary btn-sm" onClick={() => restore(l.id)}>Wiederherstellen</button>
                <button className="btn btn-danger btn-sm" onClick={() => hardDelete(l.id)}>Endgültig löschen</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

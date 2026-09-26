import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

interface CorrespondentRow {
  id: number;
  name: string;
  normalized: string;
  letter_count: number;
}

export default function KorrespondentenPage() {
  const [rows, setRows] = useState<CorrespondentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mergeMode, setMergeMode] = useState<number | null>(null);

  const load = () => {
    setLoading(true);
    api.get<CorrespondentRow[]>('/correspondents')
      .then(setRows)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const startMerge = (sourceId: number) => setMergeMode(sourceId);
  const cancelMerge = () => setMergeMode(null);

  const doMerge = async (targetId: number) => {
    if (mergeMode == null) return;
    const src = rows.find(r => r.id === mergeMode);
    const tgt = rows.find(r => r.id === targetId);
    if (!confirm(`"${src?.name}" in "${tgt?.name}" zusammenführen?\nAlle Briefe wandern, "${src?.name}" wird gelöscht.`)) return;
    try {
      await api.post(`/correspondents/${mergeMode}/merge`, { target_id: targetId });
      setMergeMode(null);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="page">
      <h1>Korrespondenten</h1>
      <p className="text-muted">
        Automatisch aus den Absendern deiner Briefe. Klick auf einen Namen → alle Briefe von diesem Absender.
        Über "Zusammenführen" Duplikate aufräumen.
      </p>
      {error && <p className="error-text">{error}</p>}
      {mergeMode != null && (
        <div className="detail-section bg-warning-soft p-4 rounded-md">
          <strong>Merge-Modus:</strong> Ziel-Eintrag in der Liste anklicken (Briefe wandern dorthin).
          <button className="btn btn-ghost btn-sm ml-4" onClick={cancelMerge}>Abbrechen</button>
        </div>
      )}
      {loading ? <p>Laden…</p> : rows.length === 0 ? (
        <p className="text-muted">Noch keine Korrespondenten. Sobald die KI einen Absender erkennt, taucht er hier auf.</p>
      ) : (
        <table className="w-full border-collapse mt-4">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left p-2">Name</th>
              <th className="text-right p-2">Briefe</th>
              <th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} className="border-b border-border">
                <td className="p-2">
                  {mergeMode != null && mergeMode !== r.id ? (
                    <button className="btn btn-secondary btn-sm" onClick={() => doMerge(r.id)}>
                      ← in {r.name} mergen
                    </button>
                  ) : (
                    <Link to={`/briefe?sender_in=${encodeURIComponent(r.name)}`}>{r.name}</Link>
                  )}
                </td>
                <td className="text-right p-2">{r.letter_count}</td>
                <td className="text-right p-2">
                  {mergeMode == null && (
                    <button className="btn btn-ghost btn-sm" onClick={() => startMerge(r.id)}>Zusammenführen…</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

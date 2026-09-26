import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';
import { Stats } from '../types';
import LetterCard from '../components/LetterCard';

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get<Stats>('/stats').then(setStats).catch(e => setError(e.message));
  }, []);

  if (error) return <div className="page"><p className="error-text">{error}</p></div>;
  if (!stats) return <div className="page"><p>Laden...</p></div>;

  const categoryEntries = Object.entries(stats.categories);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Briefkasten</h1>
          <p className="text-muted">Hallo, {user?.display_name}</p>
        </div>
        <button className="btn btn-ghost" onClick={logout}>Abmelden</button>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-value">{stats.total_letters}</span>
          <span className="stat-label">Briefe gesamt</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{stats.archived_letters}</span>
          <span className="stat-label">Archiviert</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{stats.pending_ocr}</span>
          <span className="stat-label">OCR ausstehend</span>
        </div>
      </div>

      {categoryEntries.length > 0 && (
        <section>
          <h2>Nach Kategorie</h2>
          <div className="category-list">
            {categoryEntries.map(([cat, count]) => (
              <div
                key={cat}
                className="category-row"
                onClick={() => navigate(`/briefe?category=${cat}`)}
              >
                <span>{cat}</span>
                <span className="category-count">{count}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="section-header">
          <h2>Letzte Briefe</h2>
          <button className="btn btn-ghost" onClick={() => navigate('/briefe')}>
            Alle anzeigen
          </button>
        </div>
        {stats.recent_letters.length === 0 ? (
          <p className="text-muted">Noch keine Briefe erfasst.</p>
        ) : (
          <div className="letter-list">
            {stats.recent_letters.map(l => <LetterCard key={l.id} letter={l} />)}
          </div>
        )}
      </section>
    </div>
  );
}

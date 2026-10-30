import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';

export default function KontoPage() {
  const { user, changePassword } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setDone(false);
    // Der Vergleich der beiden neuen Felder gehoert hierher und nicht in den
    // Dienst: ein Tippfehler im zweiten Feld ist keine Server-Entscheidung, und
    // ein Rueckweg ueber das Netz macht ihn nur langsamer zu sehen.
    if (next !== confirm) {
      setError('Die beiden neuen Passwörter stimmen nicht überein.');
      return;
    }
    if (next.length < 6) {
      setError('Das neue Passwort braucht mindestens 6 Zeichen.');
      return;
    }
    setLoading(true);
    try {
      await changePassword(current, next);
      setDone(true);
      setCurrent('');
      setNext('');
      setConfirm('');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Konto</h1>
          <p className="text-muted">{user?.display_name}</p>
        </div>
        <button className="btn btn-ghost" onClick={() => navigate('/')}>Zurück</button>
      </div>

      {/* Konten, deren Anmeldung bei Saganta liegt, haben hier kein Passwort zu
          aendern. Ein Formular, das nur mit 409 antworten kann, waere die
          schlechtere Antwort als dieser Satz. */}
      {user && !user.has_password ? (
        <div className="detail-section">
          <h2>Passwort</h2>
          <p className="text-muted">
            Dieses Postfach gehört zu einem Saganta-Konto. Die Anmeldung liegt dort,
            und dort wird auch das Passwort geändert.
          </p>
        </div>
      ) : (
        <div className="detail-section">
          <h2>Passwort ändern</h2>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="current">Aktuelles Passwort</label>
              <input
                id="current"
                type="password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                required
                autoFocus
                autoComplete="current-password"
              />
            </div>
            <div className="form-group">
              <label htmlFor="next">Neues Passwort</label>
              <input
                id="next"
                type="password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
                required
                minLength={6}
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label htmlFor="confirm">Neues Passwort wiederholen</label>
              <input
                id="confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                minLength={6}
                autoComplete="new-password"
              />
            </div>
            {error && <p className="error-text">{error}</p>}
            {done && (
              <p className="text-muted">
                Passwort geändert. Andere angemeldete Geräte wurden abgemeldet,
                dieses bleibt angemeldet.
              </p>
            )}
            <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
              {loading ? 'Wird geändert...' : 'Passwort ändern'}
            </button>
          </form>
          <p className="text-muted" style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
            Es gibt bewusst keinen Weg über „Passwort vergessen". Wer sein Passwort
            verliert, braucht den Betreiber des Postfachs.
          </p>
        </div>
      )}
    </div>
  );
}

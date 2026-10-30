import { useEffect, useState } from 'react';
import { api } from '../api';

interface Account {
  id: number;
  name: string;
  kind: string | null;
  correspondent_id: number | null;
  contract_number: string | null;
  monthly_amount: number | null;
  start_date: string | null;
  end_date: string | null;
  notice_period_months: number | null;
  notice_deadline: string | null;
  notes: string | null;
  is_active: boolean;
  letter_count: number;
}

interface UpcomingAccount extends Account {
  notice_deadline_resolved: string;
  days_until_notice: number;
}

const KINDS = ['Strom', 'Gas', 'Internet', 'Handy', 'Versicherung', 'Streaming', 'Abo', 'Sonstiges'];

const empty = () => ({ name: '', kind: '', contract_number: '', monthly_amount: '',
  start_date: '', end_date: '', notice_period_months: '', notes: '', is_active: true });

export default function AccountsPage() {
  const [rows, setRows] = useState<Account[]>([]);
  const [upcoming, setUpcoming] = useState<UpcomingAccount[]>([]);
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<number | 'new' | null>(null);
  const [form, setForm] = useState<any>(empty());
  const [error, setError] = useState('');

  const load = () => {
    api.get<Account[]>(`/accounts${showInactive ? '' : '?only_active=true'}`).then(setRows).catch(e => setError(e.message));
    api.get<UpcomingAccount[]>('/accounts/upcoming-notice/days?days=120').then(setUpcoming).catch(() => {});
  };

  useEffect(() => { load(); }, [showInactive]);

  const startEdit = (a: Account) => {
    setEditing(a.id);
    setForm({
      name: a.name, kind: a.kind || '', contract_number: a.contract_number || '',
      monthly_amount: a.monthly_amount?.toString() || '',
      start_date: a.start_date || '', end_date: a.end_date || '',
      notice_period_months: a.notice_period_months?.toString() || '',
      notes: a.notes || '', is_active: a.is_active,
    });
  };

  const save = async () => {
    const payload: any = { name: form.name, kind: form.kind || null,
      contract_number: form.contract_number || null,
      monthly_amount: form.monthly_amount ? parseFloat(form.monthly_amount) : null,
      start_date: form.start_date || null, end_date: form.end_date || null,
      notice_period_months: form.notice_period_months ? parseInt(form.notice_period_months) : null,
      notes: form.notes || null, is_active: !!form.is_active };
    try {
      if (editing === 'new') await api.post('/accounts', payload);
      else await api.put(`/accounts/${editing}`, payload);
      setEditing(null); load();
    } catch (e: any) {
      // PATCH-Fallback wenn PUT nicht erlaubt
      try {
        await fetch(`/api/accounts/${editing}`, {
          method: 'PATCH', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        setEditing(null); load();
      } catch (err: any) { setError(err.message); }
    }
  };

  const remove = async (id: number) => {
    if (!confirm('Konto wirklich löschen? Briefe bleiben erhalten und werden vom Konto getrennt.')) return;
    await api.del(`/accounts/${id}`);
    load();
  };

  return (
    <div className="page">
      <div className="flex justify-between items-center">
        <h1>Verträge & Konten</h1>
        <button className="btn btn-primary btn-sm" onClick={() => { setEditing('new'); setForm(empty()); }}>+ Neues Konto</button>
      </div>
      {error && <p className="error-text">{error}</p>}

      {upcoming.length > 0 && (
        <section className="detail-section bg-warning-soft rounded-md p-4 mb-4">
          <h2 className="mt-0">⏰ Anstehende Kündigungsfristen</h2>
          <ul className="mt-2 mb-0 pl-5">
            {upcoming.map(u => (
              <li key={u.id}>
                <strong>{u.name}</strong>: {u.days_until_notice} Tage ({u.notice_deadline_resolved})
              </li>
            ))}
          </ul>
        </section>
      )}

      <label className="filter-check mb-4">
        <input type="checkbox" checked={showInactive} onChange={e => setShowInactive(e.target.checked)} />
        Inaktive zeigen
      </label>

      {editing != null && (
        <section className="detail-section border border-border p-4 rounded-md mb-4">
          <h3>{editing === 'new' ? 'Neues Konto' : `Konto ${editing} bearbeiten`}</h3>
          <div className="form-group"><label>Name *</label><input value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
          <div className="form-row">
            <div className="form-group"><label>Art</label>
              <select value={form.kind} onChange={e => setForm({...form, kind: e.target.value})}>
                <option value="">–</option>
                {KINDS.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            </div>
            <div className="form-group"><label>Vertragsnummer</label><input value={form.contract_number} onChange={e => setForm({...form, contract_number: e.target.value})} /></div>
            <div className="form-group"><label>Monatlich (EUR)</label><input type="number" step="0.01" value={form.monthly_amount} onChange={e => setForm({...form, monthly_amount: e.target.value})} /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Beginn</label><input type="date" value={form.start_date} onChange={e => setForm({...form, start_date: e.target.value})} /></div>
            <div className="form-group"><label>Ende / Vertragsende</label><input type="date" value={form.end_date} onChange={e => setForm({...form, end_date: e.target.value})} /></div>
            <div className="form-group"><label>Kündigungsfrist (Monate)</label><input type="number" value={form.notice_period_months} onChange={e => setForm({...form, notice_period_months: e.target.value})} /></div>
          </div>
          <div className="form-group"><label>Notizen</label><textarea rows={2} value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} /></div>
          <label className="filter-check">
            <input type="checkbox" checked={form.is_active} onChange={e => setForm({...form, is_active: e.target.checked})} /> Aktiv
          </label>
          <div className="form-actions mt-4">
            <button className="btn btn-primary" onClick={save} disabled={!form.name}>Speichern</button>
            <button className="btn btn-ghost" onClick={() => setEditing(null)}>Abbrechen</button>
          </div>
        </section>
      )}

      {rows.length === 0 ? (
        <p className="text-muted">Noch keine Konten. Leg eins an, sobald du einen Vertrag verwalten willst.</p>
      ) : (
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left p-2">Name</th>
              <th className="text-left p-2">Art</th>
              <th className="text-right p-2">Monatl.</th>
              <th className="text-left p-2">Läuft bis</th>
              <th className="text-right p-2">Briefe</th>
              <th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} className={`border-b border-border ${r.is_active ? '' : 'opacity-50'}`}>
                <td className="p-2"><strong>{r.name}</strong>{r.contract_number && <span className="text-muted"> · {r.contract_number}</span>}</td>
                <td className="p-2">{r.kind || '–'}</td>
                <td className="text-right p-2">{r.monthly_amount != null ? `${r.monthly_amount.toFixed(2)} €` : '–'}</td>
                <td className="p-2">{r.end_date || '–'}</td>
                <td className="text-right p-2">{r.letter_count}</td>
                <td className="text-right p-2">
                  <button className="btn btn-ghost btn-sm" onClick={() => startEdit(r)}>Bearbeiten</button>
                  <button className="btn btn-danger btn-sm" onClick={() => remove(r.id)}>×</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

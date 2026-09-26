import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { LetterListItem, CATEGORIES } from '../types';
import LetterCard from '../components/LetterCard';
import SearchBar from '../components/SearchBar';

export default function BriefListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [letters, setLetters] = useState<LetterListItem[]>([]);
  const [senders, setSenders] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState(searchParams.get('category') || '');
  const [archived, setArchived] = useState(false);
  const [includeSnoozed, setIncludeSnoozed] = useState(false);
  const [search, setSearch] = useState('');
  const [searchMode, setSearchMode] = useState<'fulltext'|'semantic'>('fulltext');
  const [senderFilter, setSenderFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const load = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (category) params.set('category', category);
    if (archived) params.set('is_archived', 'true');
    if (includeSnoozed) params.set('include_snoozed', 'true');
    if (search) params.set('search', search);
    if (senderFilter) params.set('sender_in', senderFilter);
    if (dateFrom) params.set('letter_date_from', dateFrom);
    if (dateTo) params.set('letter_date_to', dateTo);
    let endpoint;
    if (search && searchMode === 'semantic') {
      endpoint = `/letters/semantic-search?q=${encodeURIComponent(search)}&limit=20`;
    } else if (search && !senderFilter && !dateFrom && !dateTo) {
      endpoint = `/search?q=${encodeURIComponent(search)}`;
    } else {
      endpoint = `/letters?${params}`;
    }
    api.get<LetterListItem[]>(endpoint)
      .then(setLetters)
      .catch(() => setLetters([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [category, archived, includeSnoozed, search, senderFilter, dateFrom, dateTo, searchMode]);
  useEffect(() => {
    api.get<string[]>('/letters/senders').then(setSenders).catch(() => setSenders([]));
  }, []);

  const clearFilters = () => {
    setCategory(''); setSenderFilter(''); setDateFrom(''); setDateTo('');
    setArchived(false); setIncludeSnoozed(false); setSearchParams({});
  };

  const hasActive = !!(category || senderFilter || dateFrom || dateTo || archived || includeSnoozed);

  return (
    <div className="page">
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        <h1>Briefe</h1>
        <Link to="/papierkorb" className="btn btn-ghost btn-sm">Papierkorb</Link>
      </div>

      <div style={{display:'flex', gap:'0.5rem', alignItems:'center'}}>
        <div style={{flex:1}}>
          <SearchBar onSearch={setSearch} placeholder={searchMode === 'semantic' ? 'Semantisch suchen (z.B. "Kuendigung Handy")…' : 'Briefe durchsuchen…'} />
        </div>
        <button
          className={'btn btn-sm ' + (searchMode === 'semantic' ? 'btn-primary' : 'btn-ghost')}
          onClick={() => setSearchMode(searchMode === 'semantic' ? 'fulltext' : 'semantic')}
          title="Zwischen Volltext und semantischer Suche umschalten"
        >
          {searchMode === 'semantic' ? '🧠 Semantisch' : '🔍 Volltext'}
        </button>
      </div>

      <div className="filter-row" style={{flexWrap:'wrap', gap:'0.5rem'}}>
        <select
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            if (e.target.value) setSearchParams({ category: e.target.value });
            else setSearchParams({});
          }}
          className="filter-select"
        >
          <option value="">Alle Kategorien</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>

        <input
          list="sender-options"
          placeholder="Absender filtern…"
          value={senderFilter}
          onChange={e => setSenderFilter(e.target.value)}
          className="filter-select"
          style={{minWidth:'180px'}}
        />
        <datalist id="sender-options">
          {senders.map(s => <option key={s} value={s} />)}
        </datalist>

        <input
          type="date"
          value={dateFrom}
          onChange={e => setDateFrom(e.target.value)}
          className="filter-select"
          title="Briefdatum ab"
        />
        <input
          type="date"
          value={dateTo}
          onChange={e => setDateTo(e.target.value)}
          className="filter-select"
          title="Briefdatum bis"
        />

        <label className="filter-check">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
          Archiviert
        </label>
        <label className="filter-check">
          <input type="checkbox" checked={includeSnoozed} onChange={(e) => setIncludeSnoozed(e.target.checked)} />
          Snoozed anzeigen
        </label>

        {hasActive && (
          <button className="btn btn-ghost btn-sm" onClick={clearFilters}>Filter zurücksetzen</button>
        )}
      </div>

      {loading ? (
        <p>Laden...</p>
      ) : letters.length === 0 ? (
        <p className="text-muted">Keine Briefe gefunden.</p>
      ) : (
        <div className="letter-list">
          {letters.map(l => <LetterCard key={l.id} letter={l} />)}
        </div>
      )}
    </div>
  );
}

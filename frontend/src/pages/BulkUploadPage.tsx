import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Letter } from '../types';

interface QueueItem {
  filename: string;
  letterId: number | null;
  error: string | null;
  status: string; // upload | processing-ocr | processing-analysis | done | error
  title: string;
  sender: string | null;
  category: string | null;
}

const TERMINAL = new Set(['done', 'error']);

export default function BulkUploadPage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const upload = async (selected: File[]) => {
    if (selected.length === 0) return;
    setUploading(true);
    const initial: QueueItem[] = selected.map(f => ({
      filename: f.name, letterId: null, error: null,
      status: 'upload', title: f.name, sender: null, category: null,
    }));
    setItems(prev => [...initial, ...prev]);
    const form = new FormData();
    for (const f of selected) form.append('files', f);
    try {
      const res = await fetch('/api/letters/bulk', {
        method: 'POST', credentials: 'same-origin', body: form,
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setItems(prev => {
        const map = new Map<string, QueueItem>();
        prev.forEach(it => map.set(it.filename + ':' + (it.letterId ?? 'pending'), it));
        for (let i = 0; i < initial.length; i++) {
          const result = data.letters[i];
          if (!result) continue;
          const key = initial[i].filename + ':pending';
          if (result.error) {
            map.set(key, { ...initial[i], error: result.error, status: 'error' });
          } else {
            const newItem: QueueItem = {
              ...initial[i], letterId: result.letter_id, status: 'processing-ocr',
              title: result.title,
            };
            map.delete(key);
            map.set(initial[i].filename + ':' + result.letter_id, newItem);
          }
        }
        return Array.from(map.values());
      });
    } catch (e: any) {
      setItems(prev => prev.map(it => it.status === 'upload' ? { ...it, status: 'error', error: e.message } : it));
    } finally {
      setUploading(false);
    }
  };

  useEffect(() => {
    const active = items.filter(it => it.letterId != null && !TERMINAL.has(it.status));
    if (active.length === 0) return;
    const t = setInterval(async () => {
      const updates = await Promise.all(active.map(async it => {
        try {
          const l = await api.get<Letter>(`/letters/${it.letterId}`);
          let st = it.status;
          if (l.analysis_status === 'done') st = 'done';
          else if (l.analysis_status === 'error') st = 'error';
          else if (l.analysis_status === 'processing') st = 'processing-analysis';
          else if (l.ocr_status === 'processing' || l.ocr_status === 'pending') st = 'processing-ocr';
          return { id: it.letterId, status: st, title: l.title, sender: l.sender, category: l.category };
        } catch {
          return null;
        }
      }));
      setItems(prev => prev.map(it => {
        const u = updates.find(u => u && u.id === it.letterId);
        return u ? { ...it, status: u.status, title: u.title, sender: u.sender, category: u.category } : it;
      }));
    }, 3000);
    return () => clearInterval(t);
  }, [items]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    upload(Array.from(e.dataTransfer.files));
  };

  const statusLabel = (s: string) => ({
    'upload': '⏳ Hochladen…',
    'processing-ocr': '📄 OCR läuft…',
    'processing-analysis': '🧠 KI-Analyse…',
    'done': '✅ Fertig',
    'error': '⚠ Fehler',
  }[s] || s);

  const summary = items.length === 0 ? null : (() => {
    const done = items.filter(it => it.status === 'done').length;
    const err = items.filter(it => it.status === 'error').length;
    return `${done}/${items.length} fertig${err ? ` · ${err} Fehler` : ''}`;
  })();

  const dropzoneCls = [
    'border-2 border-dashed p-12 text-center rounded-lg cursor-pointer mb-4 transition-colors',
    dragOver ? 'border-accent bg-accent-soft' : 'border-border bg-surface-sunken',
  ].join(' ');

  return (
    <div className="page">
      <h1>Bulk-Upload</h1>
      <p className="text-muted">Mehrere Briefe gleichzeitig hochladen: pro Datei entsteht ein eigener Brief, OCR und KI-Analyse laufen automatisch.</p>

      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileInput.current?.click()}
        className={dropzoneCls}
      >
        <div className="text-3xl mb-2">📥</div>
        <strong>Dateien hierher ziehen</strong>
        <p className="text-muted">oder klicken um Dateien auszuwählen, bis zu 50 auf einmal</p>
        <input
          ref={fileInput} type="file" multiple
          accept="image/jpeg,image/png,image/webp,application/pdf"
          className="hidden"
          onChange={e => upload(Array.from(e.target.files || []))}
        />
      </div>

      {summary && <p className="text-muted">{summary}</p>}

      {items.length > 0 && (
        <table className="letter-list w-full border-collapse">
          <thead>
            <tr>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">Titel</th>
              <th className="text-left p-2">Absender</th>
              <th className="text-left p-2">Kategorie</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it, i) => (
              <tr key={i} className="border-t border-border">
                <td className="p-2">
                  {statusLabel(it.status)}
                  {it.error && <div className="error-text text-xs">{it.error}</div>}
                </td>
                <td className="p-2">
                  {it.letterId ? <Link to={`/briefe/${it.letterId}`}>{it.title}</Link> : it.filename}
                </td>
                <td className="p-2">{it.sender || '–'}</td>
                <td className="p-2">{it.category || '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {uploading && <p>Hochladen…</p>}
    </div>
  );
}

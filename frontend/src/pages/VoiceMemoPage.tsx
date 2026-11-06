import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { voiceMemo } from '../api';

type Phase = 'idle' | 'recording' | 'review' | 'uploading';

function pickMimeType(): string {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  for (const t of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t)) return t;
  }
  return '';
}

function extForMime(mime: string): string {
  if (mime.includes('webm')) return '.webm';
  if (mime.includes('ogg')) return '.ogg';
  if (mime.includes('mp4') || mime.includes('m4a')) return '.m4a';
  return '.webm';
}

export default function VoiceMemoPage() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState('');
  const [title, setTitle] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>('');

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach(t => t.stop());
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const start = async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = pickMimeType();
      const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      rec.onstop = () => {
        const b = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' });
        setBlob(b);
        setPreviewUrl(URL.createObjectURL(b));
        setPhase('review');
        stream.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      };
      recorderRef.current = rec;
      rec.start();
      setSeconds(0);
      timerRef.current = window.setInterval(() => setSeconds(s => s + 1), 1000);
      setPhase('recording');
    } catch (e: any) {
      setError(e?.message || 'Mikrofon-Zugriff verweigert');
    }
  };

  const stop = () => {
    if (timerRef.current) { window.clearInterval(timerRef.current); timerRef.current = null; }
    recorderRef.current?.stop();
  };

  const reset = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setBlob(null);
    setPreviewUrl('');
    setSeconds(0);
    setPhase('idle');
  };

  const submit = async () => {
    if (!blob) return;
    setPhase('uploading');
    setError('');
    try {
      const mime = blob.type || 'audio/webm';
      const filename = `memo-${Date.now()}${extForMime(mime)}`;
      const letter = await voiceMemo(blob, { filename, title: title.trim() || undefined, language: 'de' });
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      navigate(`/briefe/${letter.id}`);
    } catch (e: any) {
      setError(e.message || 'Upload fehlgeschlagen');
      setPhase('review');
    }
  };

  const mmss = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;

  return (
    <div className="page">
      <h1>Sprachnotiz</h1>
      <p className="text-muted">
        Aufnehmen, anhören, hochladen. Der Service transkribiert mit faster-whisper und legt einen
        Brief mit Kategorie "Notiz" an. LLM-Analyse läuft im Hintergrund.
      </p>

      {error && <p className="error-text">{error}</p>}

      <div className="flex flex-col items-center gap-4 p-6 rounded-md bg-surface-sunken">
        <div className="font-mono text-3xl tabular-nums">{mmss}</div>

        {phase === 'idle' && (
          <button className="btn btn-primary" onClick={start}>● Aufnehmen</button>
        )}
        {phase === 'recording' && (
          <button className="btn btn-danger" onClick={stop}>■ Stoppen</button>
        )}
        {phase === 'review' && previewUrl && (
          <>
            <audio src={previewUrl} controls className="w-full max-w-md" />
            <div className="flex gap-2">
              <button className="btn btn-secondary" onClick={reset}>Neu</button>
              <button className="btn btn-primary" onClick={submit}>Hochladen + Transkribieren</button>
            </div>
          </>
        )}
        {phase === 'uploading' && <p>Transkribiere…</p>}
      </div>

      <div className="form-group mt-4">
        <label>Titel (optional)</label>
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder={`Sprachnotiz vom ${new Date().toISOString().slice(0, 10)}`}
        />
      </div>
    </div>
  );
}

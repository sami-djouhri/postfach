import { useLocation, useNavigate } from 'react-router-dom';

// Fuenf Reiter, Scannen in der Mitte unter dem Daumen. "Viele Dateien" und
// "Sprachnotiz" stehen im Kopf der Seite Erfassen.
const NAV_ITEMS = [
  { path: '/', label: 'Start', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4' },
  { path: '/briefe', label: 'Briefe', icon: 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
  { path: '/scan', label: 'Scannen', scan: true, icon: 'M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z M12 13a4 4 0 100 8 4 4 0 000-8z' },
  { path: '/upload', label: 'Erfassen', icon: 'M12 4v16m8-8H4' },
  { path: '/tags', label: 'Tags', icon: 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z' },
];

export default function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav className="bottom-nav" aria-label="Hauptnavigation">
      {NAV_ITEMS.map((item) => {
        const active = item.path === '/'
          ? location.pathname === '/'
          : location.pathname.startsWith(item.path);
        return (
          <button
            key={item.path}
            className={`bottom-nav-item ${active ? 'active' : ''} ${item.scan ? 'nav-scan' : ''}`}
            aria-current={active ? 'page' : undefined}
            onClick={() => navigate(item.path)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d={item.icon} />
            </svg>
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

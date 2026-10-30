import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './auth';
import './styles/global.css';

// Read base path from meta tag injected by reverse proxy sub_filter
const baseMeta = document.querySelector('meta[name="router-base"]');
const basename = baseMeta ? baseMeta.getAttribute('content') || '' : '';

// Export for use in api.ts and other modules
(window as any).__ROUTER_BASE__ = basename;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename={basename}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);

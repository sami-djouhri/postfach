import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { User } from './types';
import { api } from './api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<User>('/auth/me')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (username: string, password: string) => {
    const u = await api.post<User>('/auth/login', { username, password });
    setUser(u);
  };

  const register = async (username: string, password: string, displayName: string) => {
    const u = await api.post<User>('/auth/register', {
      username,
      password,
      display_name: displayName,
    });
    setUser(u);
  };

  const logout = async () => {
    await api.post('/auth/logout');
    setUser(null);
  };

  // Setzt den Benutzer NICHT neu: der Endpunkt antwortet mit 204 und das
  // Konto aendert sich nicht. Die eigene Sitzung bleibt absichtlich gueltig
  // (der Server beendet nur die anderen), ein setUser(null) wuerde hier also
  // aus einem gelungenen Wechsel einen Rauswurf machen.
  const changePassword = async (currentPassword: string, newPassword: string) => {
    await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

import { useState, useEffect } from 'react';
import { login, logout } from '@/lib/web3auth';

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing session on mount
    checkSession();
  }, []);

  async function checkSession() {
    try {
      const response = await fetch('/api/user/me');

      if (response.ok) {
        const { user } = await response.json();
        setUser(user);
      }
    } catch (error) {
      console.error('Session check failed:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleLogin() {
    try {
      const { user } = await login();
      setUser(user);
    } catch (error) {
      console.error('Login failed:', error);
    }
  }

  async function handleLogout() {
    await logout();
    setUser(null);
  }

  return {
    user,
    loading,
    login: handleLogin,
    logout: handleLogout,
    isAuthenticated: !!user,
  };
}
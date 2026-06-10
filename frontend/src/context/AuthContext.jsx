import React, { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem('jwt_token') || null);
    const [loading, setLoading] = useState(true);
    const [serverStatus, setServerStatus] = useState('checking'); // 'checking' | 'waking' | 'online'
    const navigate = useNavigate();

    // Keep the Render.com backend alive — ping /health every 10 minutes to
    // prevent the free-tier 15-minute inactivity sleep. Also detect initial
    // wake-up so we can show a banner instead of silent failures.
    useEffect(() => {
        let retryTimeout = null;
        let mounted = true;
        let attempt = 0;

        const pingHealth = async () => {
            try {
                const controller = new AbortController();
                const tid = setTimeout(() => controller.abort(), 8000);
                await fetch('/api/health', { signal: controller.signal });
                clearTimeout(tid);
                // Any HTTP response (even 5xx) means the server is reachable
                if (mounted) setServerStatus('online');
            } catch {
                if (!mounted) return;
                attempt += 1;
                if (attempt >= 2) setServerStatus('waking');
                retryTimeout = setTimeout(pingHealth, 5000);
            }
        };

        pingHealth();

        const keepAlive = setInterval(() => {
            fetch('/api/health').catch(() => {});
        }, 10 * 60 * 1000);

        return () => {
            mounted = false;
            clearTimeout(retryTimeout);
            clearInterval(keepAlive);
        };
    }, []);

    useEffect(() => {
        const verifySession = async () => {
            if (!token) {
                setLoading(false);
                return;
            }
            try {
                const response = await fetch('/api/auth/me', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (response.ok) {
                    const data = await response.json();
                    setUser({
                        id: data.id,
                        name: data.full_name,
                        email: data.email,
                        plan: data.role,
                    });
                } else if (response.status === 401 || response.status === 403) {
                    // Token is genuinely invalid or expired — log out
                    logout();
                }
                // Any other HTTP error (500 etc) — keep the user's session,
                // the server wakeup banner covers the "server is down" case
            } catch (error) {
                // Network failure (server sleeping, no internet) — do NOT log
                // out; the token may still be valid once the server is back
                console.error('Session verification failed (network):', error);
            } finally {
                setLoading(false);
            }
        };
        verifySession();
    }, [token]);

    const login = async (email, password) => {
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
            });
            let data;
            try { data = await response.json(); } catch { return { success: false, message: `Server error (${response.status})` }; }

            if (response.ok) {
                const userObj = {
                    id: data.user_id,
                    name: data.full_name,
                    email: data.email,
                    plan: data.role,
                };
                setToken(data.access_token);
                setUser(userObj);
                localStorage.setItem('jwt_token', data.access_token);
                navigate('/');
                return { success: true };
            } else {
                return { success: false, message: data.detail || 'Login failed.' };
            }
        } catch (error) {
            return { success: false, message: 'Server connection failed. Is the backend running?' };
        }
    };

    const register = async (fullName, email, password, role = 'advocate') => {
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ full_name: fullName, email, password, role }),
            });
            let data;
            try { data = await response.json(); } catch { return { success: false, message: `Server error (${response.status})` }; }

            if (response.ok) {
                const userObj = {
                    id: data.user_id,
                    name: data.full_name,
                    email: data.email,
                    plan: data.role,
                };
                setToken(data.access_token);
                setUser(userObj);
                localStorage.setItem('jwt_token', data.access_token);
                navigate('/');
                return { success: true };
            } else {
                return { success: false, message: data.detail || 'Registration failed.' };
            }
        } catch (error) {
            return { success: false, message: 'Server connection failed.' };
        }
    };

    const logout = () => {
        setToken(null);
        setUser(null);
        localStorage.removeItem('jwt_token');
        navigate('/login');
    };

    const getAuthHeaders = () => ({
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
    });

    return (
        <AuthContext.Provider value={{
            user, token, isAuthenticated: !!token,
            login, register, logout, loading, getAuthHeaders, serverStatus
        }}>
            {children}
        </AuthContext.Provider>
    );
};

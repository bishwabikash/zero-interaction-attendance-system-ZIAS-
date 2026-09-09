import { useEffect, useState } from 'react';
import { AttendanceTable } from './components/AttendanceTable';
import { DeviceList } from './components/DeviceList';
import { attendanceAPI, authAPI } from './services/api';
import './index.css';

interface Stats {
    total_students: number;
    present_today: number;
    absent_today: number;
    active_devices: number;
}

function LoginForm({ onLogin }: { onLogin: () => void }) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
            const resp = await authAPI.login(username, password);
            localStorage.setItem('zias.token', resp.data.access_token);
            onLogin();
        } catch {
            setError('Invalid credentials');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100">
            <form onSubmit={submit} className="bg-white p-8 rounded-lg shadow w-full max-w-sm space-y-4">
                <h1 className="text-2xl font-bold text-gray-900">ZIAS Admin</h1>
                <input
                    className="w-full border border-gray-300 rounded px-3 py-2"
                    placeholder="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                />
                <input
                    className="w-full border border-gray-300 rounded px-3 py-2"
                    placeholder="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                />
                {error && <div className="text-sm text-red-600">{error}</div>}
                <button
                    disabled={busy}
                    className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded py-2 font-semibold"
                >
                    {busy ? 'Signing in…' : 'Sign in'}
                </button>
            </form>
        </div>
    );
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
    const [stats, setStats] = useState<Stats | null>(null);

    useEffect(() => {
        const load = () =>
            attendanceAPI
                .getStats()
                .then((r) => setStats(r.data))
                .catch(() => {
                    /* handled by 401 interceptor */
                });
        load();
        const t = setInterval(load, 15_000);
        return () => clearInterval(t);
    }, []);

    return (
        <div className="min-h-screen bg-gray-100">
            <header className="bg-white shadow">
                <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900">ZIAS Admin Dashboard</h1>
                        <p className="text-gray-600 mt-1">Zero Interaction Attendance System</p>
                    </div>
                    <button
                        onClick={onLogout}
                        className="text-sm text-gray-500 hover:text-gray-700"
                    >
                        Sign out
                    </button>
                </div>
            </header>
            <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <StatCard label="Total students" value={stats?.total_students} tone="gray" />
                    <StatCard label="Present today" value={stats?.present_today} tone="green" />
                    <StatCard label="Absent today" value={stats?.absent_today} tone="red" />
                    <StatCard label="Active devices" value={stats?.active_devices} tone="blue" />
                </div>
                <DeviceList />
                <AttendanceTable />
            </main>
        </div>
    );
}

function StatCard({ label, value, tone }: { label: string; value: number | undefined; tone: string }) {
    const toneClass =
        tone === 'green' ? 'text-green-600'
            : tone === 'red' ? 'text-red-600'
                : tone === 'blue' ? 'text-blue-600'
                    : 'text-gray-900';
    return (
        <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm text-gray-600">{label}</div>
            <div className={`text-3xl font-bold mt-2 ${toneClass}`}>
                {value ?? '—'}
            </div>
        </div>
    );
}

function App() {
    const [authed, setAuthed] = useState<boolean>(!!localStorage.getItem('zias.token'));

    if (!authed) return <LoginForm onLogin={() => setAuthed(true)} />;

    const logout = () => {
        localStorage.removeItem('zias.token');
        setAuthed(false);
    };
    return <Dashboard onLogout={logout} />;
}

export default App;

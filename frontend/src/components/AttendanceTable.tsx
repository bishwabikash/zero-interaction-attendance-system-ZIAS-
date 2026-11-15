import { useEffect, useState } from 'react';
import { attendanceAPI } from '../services/api';

interface AttendanceRecord {
    id: number;
    student_id: string;
    student_name: string;
    room: string;
    status: 'entry' | 'exit';
    timestamp: string;
    confidence: number;
    source: string;
}

export const AttendanceTable = () => {
    const [records, setRecords] = useState<AttendanceRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        const fetchRecords = async () => {
            try {
                const response = await attendanceAPI.getRecords({ limit: 50 });
                if (!active) return;
                setRecords(response.data.records ?? []);
                setError(null);
            } catch {
                if (active) setError('Could not load attendance records');
            } finally {
                if (active) setLoading(false);
            }
        };
        void fetchRecords();
        const timer = setInterval(fetchRecords, 30_000);
        return () => {
            active = false;
            clearInterval(timer);
        };
    }, []);

    if (loading) {
        return <div className="bg-white rounded-lg shadow p-6">Loading…</div>;
    }

    return (
        <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Recent attendance</h2>
                {error && <span className="text-sm text-red-600">{error}</span>}
            </div>
            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Student</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Room</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Direction</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {records.map((r) => (
                            <tr key={r.id} className="hover:bg-gray-50">
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <div className="text-sm font-medium text-gray-900">{r.student_name}</div>
                                    <div className="text-sm text-gray-500">{r.student_id || '-'}</div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{r.room}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {new Date(r.timestamp).toLocaleString()}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <span
                                        className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${r.status === 'entry'
                                            ? 'bg-green-100 text-green-800'
                                            : 'bg-red-100 text-red-800'
                                            }`}
                                    >
                                        {r.status}
                                    </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 uppercase">
                                    {r.source}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {records.length === 0 && (
                    <div className="text-center py-8 text-gray-500">No attendance records yet</div>
                )}
            </div>
        </div>
    );
};

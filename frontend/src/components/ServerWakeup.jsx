import { useAuth } from '../context/AuthContext';
import { Loader, Wifi } from 'lucide-react';

const ServerWakeup = () => {
    const { serverStatus } = useAuth();

    if (serverStatus === 'online') return null;

    const isChecking = serverStatus === 'checking';

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.6rem',
            padding: '0.55rem 1rem',
            background: isChecking ? '#1d4ed8' : '#b45309',
            color: '#fff',
            fontSize: '0.82rem',
            fontWeight: 500,
            letterSpacing: '0.01em',
            boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
        }}>
            {isChecking
                ? <Loader size={14} className="spin" />
                : <Wifi size={14} />
            }
            <span>
                {isChecking
                    ? 'Connecting to server…'
                    : 'Server is waking up — first load takes ~30 s on Render free tier. Please wait…'
                }
            </span>
        </div>
    );
};

export default ServerWakeup;

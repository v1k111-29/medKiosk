import React, { useEffect, useState } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { Hospital, AlertCircle, Loader2 } from 'lucide-react';

const Splash: React.FC = () => {
  const { setStep } = useKioskStore();
  const { speakBoth } = useTTS();
  const [status, setStatus] = useState<'checking' | 'ready' | 'error'>('checking');

  useEffect(() => {
    const check = async () => {
      try {
        await fetch('http://localhost:8000/health');
        setStatus('ready');
        speakBoth(
          'Welcome to the hospital. Tap anywhere to begin.',
          'மருத்துவமனைக்கு வரவேற்கிறோம். தொடங்க எங்கும் தட்டவும்.'
        );
      } catch {
        setStatus('error');
      }
    };
    check();
  }, []);

  if (status === 'error') {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center bg-[#1A2B4A] text-white p-8 text-center">
        <AlertCircle size={80} className="text-red-400 mb-6" />
        <h1 className="text-4xl font-bold mb-4">System Offline</h1>
        <p className="text-xl opacity-70 max-w-md mb-8">
          Face recognition service is not responding.<br/>
          Please contact maintenance staff.
        </p>
        <button onClick={() => window.location.reload()}
          className="bg-[#2E7D96] px-10 py-4 rounded-2xl text-xl font-bold hover:bg-[#236d84] transition-colors">
          ↻ Retry
        </button>
      </div>
    );
  }

  return (
    <div
      className="h-full w-full flex flex-col items-center justify-center cursor-pointer select-none"
      style={{ background: 'linear-gradient(135deg, #1A2B4A 0%, #2E7D96 100%)' }}
      onClick={() => status === 'ready' && setStep('LANGUAGE')}
    >
      <div className="bg-white/10 backdrop-blur-sm border border-white/20 rounded-3xl p-10 flex flex-col items-center gap-6 max-w-lg w-full mx-6">
        <div className="bg-white rounded-2xl p-5 shadow-2xl">
          <Hospital size={72} className="text-[#2E7D96]" />
        </div>

        <div className="text-center text-white">
          <h1 className="text-4xl font-black mb-2 tracking-tight">அரசு மருத்துவமனை</h1>
          <h2 className="text-2xl font-semibold opacity-80">Government Hospital</h2>
        </div>

        <div className="w-full border-t border-white/20 pt-6 text-center">
          {status === 'checking' ? (
            <div className="flex items-center justify-center gap-3 text-white/60">
              <Loader2 size={20} className="animate-spin" />
              <span className="text-lg">Initialising systems…</span>
            </div>
          ) : (
            <p className="text-white/70 text-xl animate-pulse">
              👆 தொட்டு தொடரவும் · Tap anywhere to begin
            </p>
          )}
        </div>
      </div>

      <p className="mt-8 text-white/30 text-sm">Powered by AI Face Recognition</p>
    </div>
  );
};

export default Splash;

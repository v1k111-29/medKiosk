import React, { useRef, useState, useEffect, useCallback } from 'react';
import Webcam from 'react-webcam';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { faceApi } from '../services/api';
import { ScanFace, UserCheck, UserX, Loader2, AlertCircle } from 'lucide-react';

type ScanState =
  | 'init'        // server health check
  | 'idle'        // waiting for a face to appear
  | 'scanning'    // frame sent, awaiting response
  | 'found'       // known patient identified
  | 'new'         // new face, redirecting to register
  | 'no_face'     // frame had no detectable face
  | 'error';      // server unreachable

// Pulse ring colors per state
const RING: Record<ScanState, string> = {
  init:     'border-white/30',
  idle:     'border-white/50',
  scanning: 'border-[#2E7D96]',
  found:    'border-[#22C55E]',
  new:      'border-[#F59E0B]',
  no_face:  'border-red-400',
  error:    'border-red-500',
};

const STATUS_LABEL: Record<ScanState, string> = {
  init:     'Initialising…',
  idle:     'Step in front of the camera',
  scanning: 'Scanning your face…',
  found:    'Recognised! Welcome back 👋',
  new:      'New visitor — opening registration…',
  no_face:  'No face detected — please look straight',
  error:    'Camera service offline',
};

const Splash: React.FC = () => {
  const { setStep, setPatient, setTempEmbedding, setTempGender, language } = useKioskStore();
  const { speak } = useTTS();

  const webcamRef  = useRef<Webcam>(null);
  const timerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lockRef    = useRef(false);  // prevent concurrent scan requests

  const [scanState, setScanState]   = useState<ScanState>('init');
  const [patientName, setPatientName] = useState('');
  const [serverOk, setServerOk]     = useState(false);
  const [camReady, setCamReady]     = useState(false);

  // ── 1. Server health check ─────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        await fetch('/health');
        setServerOk(true);
        setScanState('idle');
        speak(
          language === 'ta'
            ? 'மருத்துவமனைக்கு வரவேற்கிறோம். கேமராவைப் பாருங்கள்.'
            : 'Welcome. Please look at the camera to check in.'
        );
      } catch {
        setScanState('error');
      }
    })();
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  // ── 2. Continuous auto-scan loop ───────────────────────────────────────────
  const doScan = useCallback(async () => {
    if (lockRef.current || !webcamRef.current || !serverOk) return;
    const imageSrc = webcamRef.current.getScreenshot();
    if (!imageSrc) return;

    lockRef.current = true;
    setScanState('scanning');

    try {
      const res  = await faceApi.post('/identify', { image: imageSrc });
      const data = res.data;

      if (data.status === 'found') {
        setScanState('found');
        setPatientName(data.name?.split(' ')[0] || 'there');
        setPatient(data);

        speak(
          language === 'ta'
            ? `வரவேற்கிறோம், ${data.name?.split(' ')[0]}!`
            : `Welcome back, ${data.name?.split(' ')[0]}!`
        );

        // Navigate after 1.8s so the user sees the "recognised" state
        setTimeout(() => {
          setStep(language === 'en' ? 'CONVERSATION' : 'MENU');
        }, 1800);
        return; // stop the loop

      } else if (data.status === 'new') {
        setScanState('new');
        setTempEmbedding(data.embedding);
        setTempGender(data.gender);
        speak(
          language === 'ta'
            ? 'புதிய நோயாளி. பதிவு செய்யவும்.'
            : 'New visitor detected. Opening registration.'
        );
        setTimeout(() => setStep('REGISTER'), 2000);
        return; // stop the loop

      } else {
        // no_face or low-confidence — stay idle and retry
        setScanState('no_face');
        timerRef.current = setTimeout(() => {
          setScanState('idle');
          lockRef.current = false;
          scheduleScan();
        }, 2000);
      }

    } catch {
      setScanState('idle');
      lockRef.current = false;
      scheduleScan();
    } finally {
      if (scanState !== 'found' && scanState !== 'new') {
        lockRef.current = false;
      }
    }
  }, [serverOk, language]);

  const scheduleScan = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(doScan, 2500);
  }, [doScan]);

  // Start loop when camera and server are both ready
  useEffect(() => {
    if (serverOk && camReady) scheduleScan();
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [serverOk, camReady]);

  // ── Helpers ────────────────────────────────────────────────────────────────
  const isActive   = ['scanning', 'found', 'new'].includes(scanState);
  const ringColor  = RING[scanState];
  const isFound    = scanState === 'found';
  const isNew      = scanState === 'new';

  return (
    <div
      className="h-full w-full flex flex-col items-center justify-between overflow-hidden select-none"
      style={{ background: 'linear-gradient(160deg, #0F1E35 0%, #1A2B4A 45%, #1A3A50 100%)' }}
    >
      {/* ── Top header ── */}
      <div className="w-full px-8 pt-8 flex items-center justify-between">
        <div>
          <h1 className="text-white font-black text-3xl tracking-tight leading-tight">
            அரசு மருத்துவமனை
          </h1>
          <p className="text-white/60 text-base font-medium">Government Hospital · Smart Kiosk</p>
        </div>
        <div className="bg-white/10 border border-white/20 rounded-2xl px-4 py-2">
          <p className="text-white/50 text-xs uppercase tracking-widest font-semibold">
            {new Date().toLocaleString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' })}
          </p>
          <p className="text-white font-bold text-lg leading-none">
            {new Date().toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })}
          </p>
        </div>
      </div>

      {/* ── Camera + overlay ── */}
      <div className="flex flex-col items-center gap-6 flex-1 justify-center py-4">

        {/* Outer glow ring */}
        <div className={`relative rounded-full p-1 transition-all duration-500 ${
          isFound  ? 'shadow-[0_0_60px_20px_rgba(34,197,94,0.35)]' :
          isNew    ? 'shadow-[0_0_60px_20px_rgba(245,158,11,0.35)]' :
          isActive ? 'shadow-[0_0_60px_20px_rgba(46,125,150,0.35)]' :
          'shadow-none'
        }`}>

          {/* Animated pulse ring */}
          {isActive && (
            <div className={`absolute inset-0 rounded-full border-4 animate-ping opacity-30 ${ringColor}`} />
          )}

          {/* Camera frame */}
          <div className={`relative rounded-full overflow-hidden border-4 transition-colors duration-500
            w-72 h-72 md:w-80 md:h-80 bg-black ${ringColor}`}>

            {scanState !== 'error' ? (
              <Webcam
                ref={webcamRef}
                screenshotFormat="image/jpeg"
                screenshotQuality={0.85}
                videoConstraints={{ facingMode: 'user', width: 640, height: 640 }}
                onUserMedia={() => setCamReady(true)}
                className="absolute inset-0 w-full h-full object-cover"
                style={{ transform: 'scaleX(-1)' }}
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                <AlertCircle size={56} className="text-red-400" />
                <p className="text-white/70 text-sm text-center px-4">Camera offline</p>
              </div>
            )}

            {/* Scan overlay */}
            {scanState === 'scanning' && (
              <div className="absolute inset-0 pointer-events-none">
                {/* Horizontal scan line */}
                <div className="absolute w-full h-0.5 bg-[#2E7D96]/80 animate-[scan_1.6s_ease-in-out_infinite]" />
                {/* Radial vignette */}
                <div className="absolute inset-0 rounded-full"
                  style={{ background: 'radial-gradient(transparent 55%, rgba(46,125,150,0.25) 100%)' }} />
              </div>
            )}

            {/* Found overlay */}
            {isFound && (
              <div className="absolute inset-0 bg-green-500/20 flex items-center justify-center">
                <UserCheck size={72} className="text-green-300 drop-shadow-lg" />
              </div>
            )}

            {/* New user overlay */}
            {isNew && (
              <div className="absolute inset-0 bg-amber-500/20 flex items-center justify-center">
                <UserX size={72} className="text-amber-300 drop-shadow-lg" />
              </div>
            )}

            {/* Corner brackets */}
            {['tl','tr','bl','br'].map(c => (
              <div key={c} className={`absolute w-8 h-8
                ${c === 'tl' ? 'top-3 left-3 border-t-4 border-l-4 rounded-tl-lg' : ''}
                ${c === 'tr' ? 'top-3 right-3 border-t-4 border-r-4 rounded-tr-lg' : ''}
                ${c === 'bl' ? 'bottom-3 left-3 border-b-4 border-l-4 rounded-bl-lg' : ''}
                ${c === 'br' ? 'bottom-3 right-3 border-b-4 border-r-4 rounded-br-lg' : ''}
                ${isFound ? 'border-green-400' : isNew ? 'border-amber-400' : 'border-[#2E7D96]'}
                transition-colors duration-300`}
              />
            ))}
          </div>
        </div>

        {/* Status label */}
        <div className="text-center space-y-1">
          <div className={`inline-flex items-center gap-2 px-5 py-2 rounded-full border transition-all duration-300 ${
            isFound  ? 'bg-green-500/20 border-green-400/50 text-green-300' :
            isNew    ? 'bg-amber-500/20 border-amber-400/50 text-amber-300' :
            scanState === 'no_face' ? 'bg-red-500/10 border-red-400/40 text-red-300' :
            'bg-white/10 border-white/20 text-white/80'
          }`}>
            {scanState === 'scanning' && <Loader2 size={14} className="animate-spin" />}
            {isFound && <UserCheck size={14} />}
            {scanState === 'no_face' && <ScanFace size={14} />}
            <span className="text-sm font-semibold">{STATUS_LABEL[scanState]}</span>
          </div>

          {isFound && patientName && (
            <p className="text-white/70 text-base font-medium animate-fade-in">
              Hello, <span className="text-green-300 font-bold">{patientName}</span>! Taking you in…
            </p>
          )}
        </div>

        {/* Live scan indicator dots */}
        {scanState === 'idle' && (
          <div className="flex items-center gap-2">
            {[0,1,2].map(i => (
              <div key={i}
                className="w-2 h-2 rounded-full bg-white/40 animate-pulse"
                style={{ animationDelay: `${i * 0.3}s` }}
              />
            ))}
            <span className="text-white/40 text-xs ml-1">Auto-scanning every 2.5s</span>
          </div>
        )}
      </div>

      {/* ── Bottom info strip ── */}
      <div className="w-full px-8 pb-8 flex items-end justify-between">
        <div className="space-y-1">
          <p className="text-white/40 text-xs uppercase tracking-widest font-semibold">AI Face Recognition</p>
          <p className="text-white/25 text-xs">Look at the camera · No touch needed</p>
        </div>

        {/* Manual fallback */}
        <button
          onClick={() => setStep('LANGUAGE')}
          className="bg-white/10 hover:bg-white/20 border border-white/20 text-white/70
            text-sm font-semibold px-5 py-3 rounded-2xl transition-all active:scale-95"
        >
          Register Manually →
        </button>
      </div>
    </div>
  );
};

export default Splash;

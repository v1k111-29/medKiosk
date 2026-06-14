import React, { useRef, useState, useEffect } from 'react';
import Webcam from 'react-webcam';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { Camera, Loader2, ScanFace } from 'lucide-react';
import { faceApi } from '../services/api';

const L = {
  en: {
    title: 'Look at the Camera',
    sub: 'Centre your face within the oval frame',
    btn: 'Scan My Face',
    scanning: 'Identifying…',
    noFace: 'No face detected. Please try again.',
    err: 'Could not connect to recognition service.',
    greet: (n: string) => `Welcome back, ${n}!`,
    newPatient: 'New patient detected. Please register.',
    tts_prompt: 'Please look straight at the camera and press Scan.',
    skip: 'Skip & Register Manually',
  },
  ta: {
    title: 'கேமராவைப் பாருங்கள்',
    sub: 'உங்கள் முகத்தை நடுவில் வைக்கவும்',
    btn: 'முக ஸ்கேன்',
    scanning: 'அடையாளம் காணப்படுகிறது…',
    noFace: 'முகம் கண்டறியவில்லை. மீண்டும் முயற்சிக்கவும்.',
    err: 'சர்வர் இணைப்பு தோல்வி.',
    greet: (n: string) => `மீண்டும் வருக, ${n}!`,
    newPatient: 'புதிய நோயாளி கண்டறியப்பட்டது. பதிவு செய்யவும்.',
    tts_prompt: 'கேமராவை நேரடியாக பாருங்கள், ஸ்கேன் அழுத்தவும்.',
    skip: 'தவிர் & நேரடியாக பதிவு செய்',
  },
};

const FaceScan: React.FC = () => {
  const webcamRef = useRef<Webcam>(null);
  const [loading, setLoading] = useState(false);
  const [errMsg, setErrMsg] = useState('');
  const { language, setStep, setPatient, setTempEmbedding, setTempGender, reset } = useKioskStore();
  const { speak } = useTTS();
  const t = L[language];

  useEffect(() => {
    speak(t.tts_prompt);
  }, []);

  const capture = async () => {
    if (!webcamRef.current) return;
    setLoading(true);
    setErrMsg('');
    const imageSrc = webcamRef.current.getScreenshot();
    if (!imageSrc) { setLoading(false); return; }

    try {
      const res = await faceApi.post('/identify', { image: imageSrc });
      const data = res.data;

      if (data.status === 'found') {
        setPatient(data);
        speak(t.greet(data.name));
        setStep('MENU');
      } else if (data.status === 'new') {
        setTempEmbedding(data.embedding);
        setTempGender(data.gender);
        speak(t.newPatient);
        setStep('REGISTER');
      } else {
        setErrMsg(t.noFace);
        speak(t.noFace);
      }
    } catch {
      setErrMsg(t.err);
      speak(t.err);
    } finally {
      setLoading(false);
    }
  };

  const handleSkip = () => {
    setTempEmbedding(null);
    setTempGender(null);
    setStep('REGISTER');
  };

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 p-8 bg-[#F2F6FA]">
      <div className="text-center">
        <h2 className="text-3xl font-bold text-[#1A2B4A] mb-1"
          style={{ fontFamily: language === 'ta' ? "'Noto Sans Tamil',sans-serif" : undefined }}>
          {t.title}
        </h2>
        <p className="text-lg text-[#4A5C78]">{t.sub}</p>
      </div>

      <div className="relative rounded-full overflow-hidden border-4 border-[#2E7D96] w-72 h-72 md:w-80 md:h-80 shadow-2xl bg-black">
        <Webcam
          ref={webcamRef}
          screenshotFormat="image/jpeg"
          videoConstraints={{ facingMode: 'user', width: 640, height: 640 }}
          className="absolute inset-0 w-full h-full object-cover"
          style={{ transform: 'scaleX(-1)' }}
        />
        {loading && (
          <div className="absolute inset-0 bg-[#2E7D96]/20 flex items-center justify-center">
            <div className="w-full h-0.5 bg-[#2E7D96]/70 absolute animate-[scan_1.6s_ease-in-out_infinite]" />
            <ScanFace size={72} className="text-white opacity-60" />
          </div>
        )}
        <div className="absolute top-3 left-3 w-7 h-7 border-t-4 border-l-4 border-[#2E7D96] rounded-tl-lg" />
        <div className="absolute top-3 right-3 w-7 h-7 border-t-4 border-r-4 border-[#2E7D96] rounded-tr-lg" />
        <div className="absolute bottom-3 left-3 w-7 h-7 border-b-4 border-l-4 border-[#2E7D96] rounded-bl-lg" />
        <div className="absolute bottom-3 right-3 w-7 h-7 border-b-4 border-r-4 border-[#2E7D96] rounded-br-lg" />
      </div>

      {errMsg && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl px-6 py-3 text-center font-medium">
          {errMsg}
        </div>
      )}

      <div className="flex flex-col w-full max-w-xs gap-4">
        <button
          onClick={capture}
          disabled={loading}
          className="flex items-center justify-center gap-3 bg-[#2E7D96] hover:bg-[#236d84] active:scale-95 disabled:opacity-50
            text-white px-8 py-5 rounded-2xl text-xl font-bold shadow-xl transition-all"
        >
          {loading
            ? <><Loader2 size={24} className="animate-spin" /> {t.scanning}</>
            : <><Camera size={24} /> {t.btn}</>
          }
        </button>

        <button
          onClick={handleSkip}
          disabled={loading}
          className="text-[#4A5C78] font-semibold hover:text-[#2E7D96] transition-all underline decoration-2 underline-offset-4 text-center"
        >
          {t.skip}
        </button>
      </div>
    </div>
  );
};

export default FaceScan;

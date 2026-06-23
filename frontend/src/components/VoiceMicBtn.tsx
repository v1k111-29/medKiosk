import React from 'react';
import { Mic, Loader2, MicOff, AlertCircle } from 'lucide-react';
import type { STTError } from '../hooks/useVoice';

interface Props {
  fieldKey: string;
  activeField: string | null;
  onClick: () => void;
  size?: number;
  /** Pass `fieldError` from useVoiceField — shows a brief error icon */
  error?: STTError;
}

const ERROR_LABELS: Record<string, { en: string; ta: string }> = {
  not_supported:     { en: 'Voice input not supported in this browser', ta: 'இந்த உலாவியில் குரல் உள்ளீடு கிடைக்கவில்லை' },
  permission_denied: { en: 'Microphone permission needed', ta: 'மைக்ரோஃபோன் அனுமதி தேவை' },
  no_speech:         { en: "Didn't catch that — tap to try again", ta: 'கேட்கவில்லை — மீண்டும் தட்டவும்' },
  network:           { en: 'Network issue — tap to retry', ta: 'நெட்வொர்க் சிக்கல் — மீண்டும் முயற்சிக்கவும்' },
  timeout:           { en: 'No response — tap to try again', ta: 'பதில் இல்லை — மீண்டும் முயற்சிக்கவும்' },
  aborted:           { en: 'Cancelled', ta: 'ரத்து செய்யப்பட்டது' },
  unknown:           { en: 'Voice input failed — tap to retry', ta: 'குரல் உள்ளீடு தோல்வி — மீண்டும் முயற்சிக்கவும்' },
};

const VoiceMicBtn: React.FC<Props> = ({ fieldKey, activeField, onClick, size = 22, error }) => {
  const active = activeField === fieldKey;
  const hasError = !active && !!error;
  const errInfo = error ? ERROR_LABELS[error] : null;

  return (
    <div className="relative ml-2 flex-shrink-0">
      <button
        type="button"
        onClick={onClick}
        title={errInfo ? errInfo.en : 'Speak this field'}
        className={`rounded-xl p-3 transition-all border-2 ${
          active
            ? 'bg-red-500 border-red-500 text-white animate-pulse shadow-lg shadow-red-200'
            : hasError
              ? 'bg-amber-50 border-amber-300 text-amber-600 hover:bg-amber-100'
              : 'bg-white border-[#DDE4EE] text-[#2E7D96] hover:bg-[#E3F2F7] hover:border-[#2E7D96]'
        }`}
      >
        {active
          ? <Loader2 size={size} className="animate-spin" />
          : hasError
            ? (error === 'permission_denied' || error === 'not_supported'
                ? <MicOff size={size} />
                : <AlertCircle size={size} />)
            : <Mic size={size} />
        }
      </button>

      {hasError && errInfo && (
        <div className="absolute left-1/2 -translate-x-1/2 top-full mt-1 z-10
          bg-[#1A2B4A] text-white text-[11px] px-2 py-1 rounded-md whitespace-nowrap
          shadow-lg pointer-events-none">
          {errInfo.en}
        </div>
      )}
    </div>
  );
};

export default VoiceMicBtn;

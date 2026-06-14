import React from 'react';
import { Mic, Loader2 } from 'lucide-react';

interface Props {
  fieldKey: string;
  activeField: string | null;
  onClick: () => void;
  size?: number;
}

const VoiceMicBtn: React.FC<Props> = ({ fieldKey, activeField, onClick, size = 22 }) => {
  const active = activeField === fieldKey;
  return (
    <button
      type="button"
      onClick={onClick}
      title="Speak this field"
      className={`ml-2 flex-shrink-0 rounded-xl p-3 transition-all border-2 ${
        active
          ? 'bg-red-500 border-red-500 text-white animate-pulse shadow-lg shadow-red-200'
          : 'bg-white border-[#DDE4EE] text-[#2E7D96] hover:bg-[#E3F2F7] hover:border-[#2E7D96]'
      }`}
    >
      {active
        ? <Loader2 size={size} className="animate-spin" />
        : <Mic size={size} />
      }
    </button>
  );
};

export default VoiceMicBtn;

import React, { useEffect, useRef, useState } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { useVoiceTriage } from '../hooks/useVoiceTriage';
import { useConversation, LLMResponse } from '../hooks/useConversation';
import { Mic, Square, Loader2, Bot, User, ChevronRight } from 'lucide-react';
import StepBar from '../components/StepBar';
import { SYMPTOM_DEPT } from '../data/departments';

const Conversation: React.FC = () => {
  const { patient, language, setStep, setTriage } = useKioskStore();
  const { speak, cancel: stopTTS } = useTTS();
  const { startRecording, stopRecording, isRecording, isProcessing, transcription } = useVoiceTriage();
  const { messages, isAILoading, processText, addMessage } = useConversation();
  const [awaitingConfirmation, setAwaiting] = useState<LLMResponse | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (language === 'ta') {
      setStep('MENU');
      return;
    }
    const name = patient?.name?.split(' ')[0] || '';
    const welcome = `Welcome back, ${name}. I am your AI assistant. How can I help you today? You can tell me your symptoms or ask for an appointment.`;
    addMessage('ai', welcome);
    speak(welcome);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, transcription]);

  const handleMicToggle = async () => {
    if (isRecording) {
      stopRecording();
    } else {
      stopTTS();
      await startRecording();
    }
  };

  useEffect(() => {
    if (!isRecording && transcription.trim() && !isProcessing) {
      handleUserSpeech(transcription);
    }
  }, [isRecording, isProcessing]);

  const handleUserSpeech = async (text: string) => {
    if (awaitingConfirmation) {
      const lower = text.toLowerCase();
      if (lower.includes('yes') || lower.includes('yeah') || lower.includes('correct') || lower.includes('sure') || lower.includes('okay')) {
        speak("Great. Let's get you routed to the right department.");
        const dept = SYMPTOM_DEPT[awaitingConfirmation.department || 'general'] || SYMPTOM_DEPT['general'];
        setTriage({
          symptoms: awaitingConfirmation.symptoms || '',
          deptId: dept.id,
          deptName: dept.en,
          deptNameTa: dept.ta,
          room: dept.room,
          waitMins: dept.waitMins,
        });
        setStep('DEPARTMENT');
      } else {
        setAwaiting(null);
        const retry = "I see. Could you please describe your symptoms again or tell me which department you need?";
        addMessage('ai', retry);
        speak(retry);
      }
      return;
    }

    const response = await processText(text);
    if (response) {
      speak(response.reply);
      if (response.intent === 'symptoms' && response.department) {
        setAwaiting(response);
      }
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#F2F6FA]">
      <div className="p-4">
        <StepBar />
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 space-y-4 py-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'ai' ? 'justify-start' : 'justify-end'}`}>
            <div className={`flex gap-3 max-w-[80%] ${m.role === 'ai' ? 'flex-row' : 'flex-row-reverse'}`}>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 
                ${m.role === 'ai' ? 'bg-[#2E7D96] text-white' : 'bg-white text-[#4A5C78] border-2 border-[#DDE4EE]'}`}>
                {m.role === 'ai' ? <Bot size={20} /> : <User size={20} />}
              </div>
              <div className={`p-4 rounded-2xl shadow-sm text-lg font-medium
                ${m.role === 'ai' 
                  ? 'bg-white text-[#1A2B4A] rounded-tl-none' 
                  : 'bg-[#2E7D96] text-white rounded-tr-none'}`}>
                {m.text}
              </div>
            </div>
          </div>
        ))}
        {isRecording && (
          <div className="flex justify-end">
            <div className="bg-[#E3F2F7] text-[#2E7D96] p-4 rounded-2xl border-2 border-[#2E7D96] animate-pulse">
              Listening: {transcription}...
            </div>
          </div>
        )}
        {isAILoading && (
          <div className="flex justify-start">
            <div className="bg-white p-4 rounded-2xl flex items-center gap-3 text-[#2E7D96]">
              <Loader2 className="animate-spin" /> Thinking...
            </div>
          </div>
        )}
      </div>

      <div className="p-8 bg-white border-t border-[#DDE4EE] flex items-center gap-6">
        <button
          onClick={handleMicToggle}
          disabled={isAILoading}
          className={`w-24 h-24 rounded-full flex items-center justify-center transition-all shadow-xl active:scale-95
            ${isRecording ? 'bg-red-500 text-white animate-pulse' : 'bg-[#2E7D96] text-white hover:bg-[#236d84]'}`}
        >
          {isRecording ? <Square size={32} /> : <Mic size={32} />}
        </button>
        <div className="flex-1">
          <p className="text-[#8A9BB5] font-semibold uppercase tracking-widest text-xs mb-1">
            {isRecording ? 'Recording...' : 'Tap the mic and speak'}
          </p>
          <h3 className="text-xl font-bold text-[#1A2B4A]">
            {isRecording ? 'I am listening to you...' : 'How can I help you today?'}
          </h3>
        </div>
        <button onClick={() => setStep('MENU')} className="px-6 py-4 rounded-xl border-2 border-[#DDE4EE] text-[#4A5C78] font-bold flex items-center gap-2 hover:bg-gray-50">
          Use Touch Menu <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
};

export default Conversation;

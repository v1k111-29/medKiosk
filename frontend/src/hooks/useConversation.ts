import { useState, useCallback, useRef } from 'react';
import { faceApi } from '../services/api';
import { useKioskStore } from '../store/useKioskStore';

export interface LLMResponse {
  intent: 'symptoms' | 'greeting' | 'other';
  department: string | null;
  symptoms: string | null;
  urgency: 'normal' | 'urgent' | 'emergency';
  confidence: number;
  reply: string;
}

export const useConversation = () => {
  const [messages, setMessages] = useState<{ role: 'ai' | 'user'; text: string }[]>([]);
  const [isAILoading, setIsAI] = useState(false);

  // useRef instead of state for the error counter — avoids the stale-closure
  // problem where `errorCount` read inside `processText` was always the
  // value from the render that created the closure, not the latest one.
  const errorCountRef = useRef(0);

  const { setStep, setTriage, language } = useKioskStore();

  const addMessage = useCallback((role: 'ai' | 'user', text: string) => {
    setMessages(prev => [...prev, { role, text }]);
  }, []);

  const processText = useCallback(async (text: string): Promise<LLMResponse | null> => {
    const trimmed = text.trim();
    if (!trimmed) return null;

    addMessage('user', trimmed);
    setIsAI(true);

    try {
      const res = await faceApi.post('/conversation/triage', {
        text: trimmed,
        language,
      });

      const data: LLMResponse = res.data;
      addMessage('ai', data.reply);
      errorCountRef.current = 0; // reset on success

      if (data.intent === 'symptoms' && data.department && data.confidence > 0.6) {
        setTriage({
          symptoms: data.symptoms || trimmed,
          deptId: data.department,
        });
      }

      return data;
    } catch (err) {
      console.error('[Conversation] LLM call failed:', err);
      errorCountRef.current += 1;

      const fallbackMsg = errorCountRef.current >= 2
        ? "I'm having trouble connecting to my brain. Let's use the touch menu instead."
        : "Sorry, I'm having a little trouble. Could you say that again?";

      addMessage('ai', fallbackMsg);

      if (errorCountRef.current >= 2) {
        setTimeout(() => setStep('MENU'), 2500);
      }
      return null;
    } finally {
      setIsAI(false);
    }
  }, [addMessage, language, setTriage, setStep]);

  return { messages, isAILoading, processText, addMessage, errorCount: errorCountRef.current };
};

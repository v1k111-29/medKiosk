import { useState, useCallback } from 'react';
import { whisperApi } from '../services/api';
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
  const [errorCount, setErrors] = useState(0);
  const { setStep, setTriage, language } = useKioskStore();

  const addMessage = useCallback((role: 'ai' | 'user', text: string) => {
    setMessages(prev => [...prev, { role, text }]);
  }, []);

  const processText = async (text: string) => {
    addMessage('user', text);
    setIsAI(true);

    try {
      const res = await whisperApi.post('/conversation', {
        text,
        language: language
      });
      
      const data: LLMResponse = res.data;
      addMessage('ai', data.reply);
      
      // Handle Intent: Symptoms & Department Found
      if (data.intent === 'symptoms' && data.department && data.confidence > 0.6) {
        // We'll let the view handle the "Yes/No" confirmation
        // But we pre-set the triage data in the store
        setTriage({
          symptoms: data.symptoms || text,
          deptId: data.department,
          // We need to map deptId to names (logic can be in store or helper)
        });
        return data;
      }

      setErrors(0); // Reset errors on successful LLM call
      return data;

    } catch (err) {
      console.error("LLM Call Failed:", err);
      setErrors(prev => prev + 1);
      const fallbackMsg = "I'm sorry, I'm having trouble connecting to my brain. Let's use the touch menu instead.";
      addMessage('ai', fallbackMsg);
      
      if (errorCount >= 1) {
        // Fallback to manual menu if LLM fails twice
        setTimeout(() => setStep('MENU'), 3000);
      }
      return null;
    } finally {
      setIsAI(false);
    }
  };

  return { messages, isAILoading, processText, addMessage, errorCount };
};

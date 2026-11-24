/**
 * Privacy helpers shared by the idle reset and the error boundary.
 */
import { stopSpeaking } from './services/tts';

/** Stop every camera/mic track attached to a media element, and cancel speech. */
export function stopAllMedia(): void {
  try {
    document.querySelectorAll<HTMLMediaElement>('video, audio').forEach((el) => {
      const src = el.srcObject;
      if (src && typeof (src as MediaStream).getTracks === 'function') {
        (src as MediaStream).getTracks().forEach((t) => t.stop());
      }
      el.srcObject = null;
    });
  } catch { /* ignore */ }
  stopSpeaking(); // Sarvam audio + browser speech
}

/** "9876543210" -> "******3210" */
export function maskPhone(phone: string): string {
  const digits = phone.replace(/\D/g, '');
  return `******${digits.slice(-4)}`;
}

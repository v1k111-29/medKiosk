import { useCallback, useEffect, useState } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { stopAllMedia } from '../utils';

export const IDLE_MS = 90_000;
export const WARN_SECONDS = 10;

const EVENTS = ['pointerdown', 'pointermove', 'mousemove', 'touchstart', 'keydown', 'wheel'] as const;

/**
 * Privacy reset for a shared kiosk. After IDLE_MS without input on any step
 * except SPLASH, `remaining` counts down from WARN_SECONDS; at zero media is
 * stopped and the store is reset (clearing patient data) back to SPLASH.
 */
export function useIdleReset() {
  const step = useKioskStore((s) => s.step);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [nonce, setNonce] = useState(0);

  const dismiss = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (step === 'SPLASH') {
      setRemaining(null);
      return;
    }
    let idleTimer: ReturnType<typeof setTimeout> | undefined;
    let tick: ReturnType<typeof setInterval> | undefined;
    let warning = false;

    const clearTimers = () => {
      if (idleTimer) clearTimeout(idleTimer);
      if (tick) clearInterval(tick);
      idleTimer = undefined;
      tick = undefined;
    };

    const startWarning = () => {
      warning = true;
      let left = WARN_SECONDS;
      setRemaining(left);
      tick = setInterval(() => {
        left -= 1;
        if (left <= 0) {
          clearTimers();
          warning = false;
          stopAllMedia();
          setRemaining(null);
          useKioskStore.getState().reset();
        } else {
          setRemaining(left);
        }
      }, 1000);
    };

    const startIdle = () => {
      clearTimers();
      warning = false;
      setRemaining(null);
      idleTimer = setTimeout(startWarning, IDLE_MS);
    };

    const onActivity = (e: Event) => {
      // Ignore jitter-type events while the countdown is showing; an
      // explicit tap/key dismisses it.
      if (warning && (e.type === 'mousemove' || e.type === 'pointermove' || e.type === 'wheel')) return;
      startIdle();
    };

    EVENTS.forEach((ev) => window.addEventListener(ev, onActivity, { passive: true }));
    startIdle();

    return () => {
      clearTimers();
      EVENTS.forEach((ev) => window.removeEventListener(ev, onActivity));
    };
  }, [step, nonce]);

  return { remaining, dismiss };
}

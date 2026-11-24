import React from 'react';
import i18n from '../i18n';
import { useKioskStore } from '../store/useKioskStore';
import { stopAllMedia } from '../utils';

interface Props { children: React.ReactNode }
interface State { hasError: boolean }

/** Top-level boundary: any render crash shows a restart screen that wipes kiosk state. */
class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  restart = () => {
    stopAllMedia();
    useKioskStore.getState().reset();
    this.setState({ hasError: false });
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    const en = i18n.getFixedT('en');
    const ta = i18n.getFixedT('ta');
    return (
      <button
        onClick={this.restart}
        className="h-screen w-full bg-[#F2F6FA] flex flex-col items-center justify-center gap-4 p-8 text-center"
      >
        <span className="text-6xl">⚠️</span>
        <span className="text-4xl font-black text-[#1A2B4A]">{en('error_title')} — {en('error_tap')}</span>
        <span className="text-4xl font-black text-[#1A2B4A]" style={{ fontFamily: "'Noto Sans Tamil',sans-serif" }}>
          {ta('error_title')} — {ta('error_tap')}
        </span>
      </button>
    );
  }
}

export default ErrorBoundary;

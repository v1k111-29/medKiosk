import React, { useEffect } from 'react';
import { useKioskStore } from './store/useKioskStore';
import Splash from './views/Splash';
import LanguageSelect from './views/LanguageSelect';
import FaceScan from './views/FaceScan';
import Registration from './views/Registration';
import MainMenu from './views/MainMenu';
import Conversation from './views/Conversation';
import Triage from './views/Triage';
import Department from './views/Department';
import Vitals from './views/Vitals';
import Confirmation from './views/Confirmation';
import Consent from './views/Consent';
import PhoneVerify from './views/PhoneVerify';
import EmergencyAlert from './views/EmergencyAlert';
import IdleOverlay from './components/IdleOverlay';

const App: React.FC = () => {
  const step = useKioskStore((s) => s.step);
  const loadDepartments = useKioskStore((s) => s.loadDepartments);

  // Departments come from the API; load once and cache in the store.
  useEffect(() => { void loadDepartments(); }, [loadDepartments]);

  const renderStep = () => {
    switch (step) {
      // SPLASH: always-on camera, match-only (returning consented patients; nothing
      // returned or stored for a non-match). New/unknown visitors -> CONSENT first.
      // CONSENT -> SCAN (agreed, template may be stored) or PHONE (declined, OTP).
      case 'SPLASH':       return <Splash />;
      case 'LANGUAGE':     return <LanguageSelect />;
      case 'CONSENT':      return <Consent />;
      case 'PHONE':        return <PhoneVerify />;
      case 'SCAN':         return <FaceScan />;
      case 'REGISTER':     return <Registration />;
      case 'MENU':         return <MainMenu />;
      case 'CONVERSATION': return <Conversation />;
      case 'TRIAGE':       return <Triage />;
      case 'DEPARTMENT':   return <Department />;
      case 'VITALS':       return <Vitals />;
      case 'CONFIRM':      return <Confirmation />;
      case 'EMERGENCY':    return <EmergencyAlert />;
      default:             return <Splash />;
    }
  };

  return (
    <div className="h-screen w-full bg-[#F2F6FA] flex flex-col overflow-hidden font-sans">
      {renderStep()}
      <IdleOverlay />
    </div>
  );
};

export default App;

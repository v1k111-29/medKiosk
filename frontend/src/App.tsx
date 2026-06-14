import React, { useEffect } from 'react';
import { useKioskStore } from './store/useKioskStore';
import StepBar from './components/StepBar';
import Splash from './views/Splash';
import LanguageSelect from './views/LanguageSelect';
import FaceScan from './views/FaceScan';
import Registration from './views/Registration';
import MainMenu from './views/MainMenu';
import Triage from './views/Triage';
import Department from './views/Department';
import Vitals from './views/Vitals';
import Confirmation from './views/Confirmation';

const SHOW_STEPBAR: string[] = ['SCAN','REGISTER','MENU','TRIAGE','DEPARTMENT','VITALS','CONFIRM'];

const App: React.FC = () => {
  const { step, reset } = useKioskStore();

  // Global idle reset — 90 seconds after any non-SPLASH step
  useEffect(() => {
    if (step === 'SPLASH' || step === 'LANGUAGE') return;
    const timer = setTimeout(() => reset(), 90_000);
    return () => clearTimeout(timer);
  }, [step, reset]);

  return (
    <div className="h-screen w-screen bg-[#F2F6FA] text-[#1A2B4A] font-sans flex flex-col overflow-hidden">
      {SHOW_STEPBAR.includes(step) && <StepBar />}

      <div className="flex-1 overflow-hidden">
        {step === 'SPLASH'      && <Splash />}
        {step === 'LANGUAGE'    && <LanguageSelect />}
        {step === 'SCAN'        && <FaceScan />}
        {step === 'REGISTER'    && <Registration />}
        {step === 'MENU'        && <MainMenu />}
        {step === 'TRIAGE'      && <Triage />}
        {step === 'DEPARTMENT'  && <Department />}
        {step === 'VITALS'      && <Vitals />}
        {step === 'CONFIRM'     && <Confirmation />}
      </div>
    </div>
  );
};

export default App;

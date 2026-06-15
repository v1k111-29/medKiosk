import React from 'react';
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

const App: React.FC = () => {
  const { step } = useKioskStore();

  const renderStep = () => {
    switch (step) {
      case 'SPLASH':      return <Splash />;
      case 'LANGUAGE':    return <LanguageSelect />;
      case 'SCAN':        return <FaceScan />;
      case 'REGISTER':    return <Registration />;
      case 'MENU':        return <MainMenu />;
      case 'CONVERSATION': return <Conversation />;
      case 'TRIAGE':      return <Triage />;
      case 'DEPARTMENT':  return <Department />;
      case 'VITALS':      return <Vitals />;
      case 'CONFIRM':     return <Confirmation />;
      default:            return <Splash />;
    }
  };

  return (
    <div className="h-screen w-full bg-[#F2F6FA] flex flex-col overflow-hidden font-sans">
      {renderStep()}
    </div>
  );
};

export default App;

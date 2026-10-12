import Footer from "./Footer";
import Header from "./Header";
import { LangContext, useLang } from "./i18n";
import Fallback from "./scene/Fallback";
import SceneSlot from "./scene/SceneSlot";
import AccessRequest from "./sections/AccessRequest";
import Checks from "./sections/Checks";
import Hero from "./sections/Hero";
import HowItWorks from "./sections/HowItWorks";
import Languages from "./sections/Languages";
import LiveExample from "./sections/LiveExample";
import Problem from "./sections/Problem";
import Research from "./sections/Research";
import Security from "./sections/Security";

export default function LandingPage() {
  const lang = useLang();
  return (
    <LangContext.Provider value={lang}>
      <div className="min-h-full bg-paper text-ink">
        <Header />
        <main>
          {/* the scene stays beside the first three blocks while they scroll by */}
          <div className="max-w-6xl mx-auto grid md:grid-cols-[1fr_minmax(0,46%)]">
            <div><Hero /><Problem /><HowItWorks /></div>
            <div className="hidden md:block">
              <div className="sticky top-14 h-[calc(100vh-3.5rem)] flex items-center p-6"><SceneSlot /></div>
            </div>
          </div>
          <div className="md:hidden px-4 pb-8"><Fallback /></div>
          <LiveExample />
          <Checks />
          <Languages />
          <Research />
          <Security />
          <AccessRequest />
        </main>
        <Footer />
      </div>
    </LangContext.Provider>
  );
}

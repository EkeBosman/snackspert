import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { Linking } from 'react-native';
import { loadEngagement, saveEngagement, EngagementState } from '../services/engagement';
import { FollowModal } from '../components/FollowModal';
import { SocialKanaal } from '../constants/socials';

interface EngagementContextValue {
  /** Registreer een betekenisvolle actie (recensie bekeken, favoriet, filter, ...). */
  markActie: () => void;
}

const EngagementContext = createContext<EngagementContextValue | null>(null);

const DERTIG_DAGEN = 30 * 24 * 60 * 60 * 1000;
const TIMER_2MIN = 2 * 60 * 1000;
// Minimale tijd sinds openen voordat een actie de modal mag triggeren, zodat
// hij nooit vlak na het openen verschijnt.
const MIN_DWELL = 25 * 1000;

function magTonen(s: EngagementState): boolean {
  if (s.gevolgd) return false;
  if (s.opens < 8) return false;
  if (!s.heeftActie) return false;
  if (s.laatstGetoond && Date.now() - s.laatstGetoond < DERTIG_DAGEN) return false;
  return true;
}

async function openKanaal(k: SocialKanaal): Promise<void> {
  try {
    if (await Linking.canOpenURL(k.app)) {
      await Linking.openURL(k.app);
      return;
    }
  } catch {}
  try {
    await Linking.openURL(k.web);
  } catch {}
}

export function EngagementProvider({ children }: { children: ReactNode }) {
  const stateRef = useRef<EngagementState | null>(null);
  const sessieStart = useRef<number>(0);
  const getoondSessie = useRef(false);
  const [, setTick] = useState(0); // forceer render bij statuswijziging
  const [modalZichtbaar, setModalZichtbaar] = useState(false);

  const evalueer = useCallback(() => {
    const s = stateRef.current;
    if (!s || getoondSessie.current) return;
    if (Date.now() - sessieStart.current < MIN_DWELL) return;
    if (!magTonen(s)) return;

    getoondSessie.current = true;
    const n = { ...s, laatstGetoond: Date.now() };
    stateRef.current = n;
    saveEngagement(n);
    setModalZichtbaar(true);
  }, []);

  const markActie = useCallback(() => {
    const s = stateRef.current;
    if (!s) return;
    if (!s.heeftActie) {
      const n = { ...s, heeftActie: true };
      stateRef.current = n;
      saveEngagement(n);
    }
    evalueer();
  }, [evalueer]);

  // Bij opstarten: state laden, opens ophogen, 2-minuten-timer starten.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    sessieStart.current = Date.now();

    (async () => {
      const s = await loadEngagement();
      s.opens += 1;
      stateRef.current = s;
      await saveEngagement(s);
      setTick(t => t + 1);

      // Na 2 minuten actief telt dat zelf als betekenisvolle actie.
      timer = setTimeout(() => markActie(), TIMER_2MIN);
    })();

    return () => clearTimeout(timer);
  }, [markActie]);

  const onKies = useCallback(async (k: SocialKanaal) => {
    await openKanaal(k);
    const s = stateRef.current;
    if (s) {
      const n = { ...s, gevolgd: true };
      stateRef.current = n;
      await saveEngagement(n);
    }
    setModalZichtbaar(false);
  }, []);

  const onDismiss = useCallback(() => {
    setModalZichtbaar(false);
  }, []);

  return (
    <EngagementContext.Provider value={{ markActie }}>
      {children}
      <FollowModal visible={modalZichtbaar} onKies={onKies} onDismiss={onDismiss} />
    </EngagementContext.Provider>
  );
}

export function useEngagement() {
  const ctx = useContext(EngagementContext);
  // Veilige no-op als de provider (nog) niet aanwezig is.
  if (!ctx) return { markActie: () => {} };
  return ctx;
}

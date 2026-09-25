/**
 * The player's position, as continuously as the phone will give it.
 *
 * Two things matter here beyond "get a fix". Battery, because this runs for four hours
 * alongside the screen and later the microphone — so we ask for updates by distance moved
 * rather than on a timer, and a player standing still costs nothing. And honesty: a fix
 * with 40 m of error is worse than useless for a yardage, so accuracy is surfaced rather
 * than hidden.
 */

import * as Location from "expo-location";
import { useEffect, useRef, useState } from "react";

export type LocationState = {
  coords: { latitude: number; longitude: number } | null;
  /** Radius of uncertainty in metres, as reported by the phone. */
  accuracyM: number | null;
  status: "starting" | "denied" | "unavailable" | "tracking";
  error: string | null;
};

/** Below this, the fix is good enough to quote a yardage from. */
export const GOOD_ACCURACY_M = 12;

export function useLocation(enabled = true): LocationState {
  const [state, setState] = useState<LocationState>({
    coords: null,
    accuracyM: null,
    status: "starting",
    error: null,
  });

  const subscription = useRef<Location.LocationSubscription | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    (async () => {
      try {
        const { granted } = await Location.requestForegroundPermissionsAsync();
        if (cancelled) return;

        if (!granted) {
          setState((s) => ({ ...s, status: "denied" }));
          return;
        }

        subscription.current = await Location.watchPositionAsync(
          {
            accuracy: Location.Accuracy.High,
            // A golfer who hasn't moved 3 m hasn't changed their shot.
            distanceInterval: 3,
            timeInterval: 2000,
          },
          (position) => {
            if (cancelled) return;
            setState({
              coords: {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
              },
              accuracyM: position.coords.accuracy ?? null,
              status: "tracking",
              error: null,
            });
          },
        );
      } catch (e) {
        if (!cancelled) {
          setState((s) => ({
            ...s,
            status: "unavailable",
            error: e instanceof Error ? e.message : String(e),
          }));
        }
      }
    })();

    return () => {
      cancelled = true;
      subscription.current?.remove();
      subscription.current = null;
    };
  }, [enabled]);

  return state;
}

/** Metres between two lat/lon points. Good enough for "have I moved?" checks. */
export function metresBetween(
  a: { latitude: number; longitude: number },
  b: { latitude: number; longitude: number },
): number {
  const R = 6_371_000;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.latitude - a.latitude);
  const dLon = toRad(b.longitude - a.longitude);
  const lat1 = toRad(a.latitude);
  const lat2 = toRad(b.latitude);

  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

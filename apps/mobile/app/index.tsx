/**
 * The hole screen — the one you actually use on the course.
 *
 * Map-dominant on purpose: the course fills the screen and the numbers float over it, so
 * you read the shot spatially rather than as a table. Everything shown here comes from the
 * engine; nothing is invented on the client.
 *
 * Position drives the screen. Which hole you're on is inferred from where you're standing
 * rather than asked for, and the yardages follow you down the fairway. The arrows are there
 * for when you want to look ahead — taking one hands control back to you until you tap the
 * GPS chip to resume.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Path } from "react-native-svg";

import {
  api,
  ApiError,
  API_BASE_URL,
  type Course,
  type Located,
  type Recommendation,
} from "../src/api/client";
import { HoleMap } from "../src/components/HoleMap";
import {
  GhostButton,
  GlassPanel,
  IconButton,
  OutcomeBar,
  PrimaryButton,
  RiskChip,
} from "../src/components/ui";
import { DevPanel, type SimulatedFix } from "../src/dev/DevPanel";
import { GOOD_ACCURACY_M, metresBetween, useLocation } from "../src/hooks/useLocation";
import { colors, font, glass, radius, type } from "../src/theme";

const HANDICAP = 15;

/**
 * How far you have to walk before the engine re-simulates.
 *
 * Distances update continuously because they're just geometry. A recommendation is
 * thousands of simulated shots, and it doesn't meaningfully change over a few paces.
 */
const RESIMULATE_AFTER_M = 10;

export default function HoleScreen() {
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();

  const [simulated, setSimulated] = useState<SimulatedFix>(null);

  // A simulated fix stands in for the real one entirely, so every downstream behaviour is
  // the on-course behaviour. Nothing below here knows which it got.
  const realGps = useLocation(!simulated);
  const gps = simulated
    ? { coords: simulated, accuracyM: 4, status: "tracking" as const, error: null }
    : realGps;

  const [course, setCourse] = useState<Course | null>(null);
  const [holeNumber, setHoleNumber] = useState(1);
  const [located, setLocated] = useState<Located | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [followingGps, setFollowingGps] = useState(true);

  const lastSimulatedFrom = useRef<{ latitude: number; longitude: number } | null>(null);

  /**
   * Responses can arrive out of order — a request made two paces ago may land after one
   * made just now. Without this the yardage walks backwards as you walk forwards, which
   * looks exactly like a broken rangefinder.
   */
  const locateSeq = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const courses = await api.courses();
        if (courses.length === 0) {
          setError("No courses imported yet. Run the importer, then reload.");
          return;
        }
        const loaded = await api.course(courses[0].course_id);
        if (!cancelled) setCourse(loaded);
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const usingGps = Boolean(gps.coords && located?.on_course);

  // Distances follow you continuously — this is cheap geometry, not a simulation.
  useEffect(() => {
    if (!course || !gps.coords) return;
    let cancelled = false;
    const seq = ++locateSeq.current;

    api
      .locate(course.course_id, gps.coords.latitude, gps.coords.longitude)
      .then((next) => {
        // Drop anything a newer request has already superseded.
        if (cancelled || seq !== locateSeq.current) return;
        setLocated(next);
        if (followingGps && next.on_course) setHoleNumber(next.hole);
      })
      .catch(() => {
        // A failed locate just means the distances go stale for a beat; the last
        // recommendation is still on screen and still correct for where it was taken.
      });

    return () => {
      cancelled = true;
    };
  }, [course, gps.coords, followingGps]);

  const loadRecommendation = useCallback(
    async (courseId: string, hole: number, from: { latitude: number; longitude: number } | null) => {
      setThinking(true);
      setError(null);
      try {
        const next = await api.recommend({
          course_id: courseId,
          hole,
          handicap: HANDICAP,
          samples: 2000,
          ...(from ? { start_latlon: [from.latitude, from.longitude] as [number, number] } : {}),
        });
        setRecommendation(next);
        lastSimulatedFrom.current = from;
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
        setRecommendation(null);
      } finally {
        setThinking(false);
      }
    },
    [],
  );

  // Re-simulate when the hole changes, or when you've walked far enough to matter.
  useEffect(() => {
    if (!course) return;

    const from = usingGps && gps.coords ? gps.coords : null;
    const previous = lastSimulatedFrom.current;

    const holeChanged = recommendation?.hole !== holeNumber;
    const movedEnough =
      from && previous ? metresBetween(previous, from) >= RESIMULATE_AFTER_M : from !== previous;

    if (holeChanged || movedEnough) {
      loadRecommendation(course.course_id, holeNumber, from);
    }
  }, [course, holeNumber, usingGps, gps.coords, recommendation?.hole, loadRecommendation]);

  const hole = course?.holes.find((h) => h.number === holeNumber) ?? null;
  const holeCount = course?.holes.length ?? 18;
  const trouble = (recommendation?.hazards ?? []).reduce((sum, h) => sum + h.probability, 0);

  // How much wind and elevation move the number. Null when they don't, which is the case
  // until live weather is wired in — and a "plays like" equal to the yardage is noise.
  const playsLikeDelta =
    recommendation && Math.abs(recommendation.plays_like_yards - recommendation.to_pin_yards) >= 2
      ? recommendation.plays_like_yards - recommendation.to_pin_yards
      : null;

  const mapInset = useMemo(
    () => ({ top: insets.top + 84, bottom: insets.bottom + 300 }),
    [insets.top, insets.bottom],
  );

  const stepHole = (delta: number) => {
    setFollowingGps(false);
    setHoleNumber((n) => Math.min(holeCount, Math.max(1, n + delta)));
  };

  if (error && !course) {
    return (
      <View style={[styles.center, { paddingTop: insets.top }]}>
        <Text style={styles.errorTitle}>Can't reach the caddie</Text>
        <Text style={styles.errorBody}>{error}</Text>
        <Text style={styles.errorHint}>{API_BASE_URL}</Text>
      </View>
    );
  }

  if (!course || !hole) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <HoleMap hole={hole} recommendation={recommendation} width={width} height={height} inset={mapInset} />

      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <IconButton label="Previous hole" onPress={() => stepHole(-1)}>
          <Chevron direction="left" />
        </IconButton>

        <View style={{ flex: 1, gap: 3 }}>
          <Text style={type.title}>HOLE {hole.number}</Text>
          <View style={styles.metaRow}>
            <Text style={type.meta}>PAR {hole.par ?? "?"}</Text>
            <View style={styles.dot} />
            <Text style={type.meta} numberOfLines={1}>
              {course.name.toUpperCase()}
            </Text>
          </View>
        </View>

        <IconButton label="Next hole" onPress={() => stepHole(1)}>
          <Chevron direction="right" />
        </IconButton>
      </View>

      <View style={[styles.statusRow, { top: insets.top + 82 }]}>
        {__DEV__ ? (
          <DevPanel
            courseId={course.course_id}
            holeCount={holeCount}
            active={simulated !== null}
            onFix={(fix) => {
              setSimulated(fix);
              setFollowingGps(true);
            }}
            onClear={() => setSimulated(null)}
          />
        ) : null}
        <GpsChip
          gps={gps}
          located={located}
          following={followingGps}
          simulated={simulated !== null}
          onResume={() => setFollowingGps(true)}
        />
      </View>

      {located?.on_course ? (
        <GreenDistances located={located} top={insets.top + 82} />
      ) : null}

      <GlassPanel style={[styles.card, { bottom: insets.bottom + 104 }]}>
        <View style={styles.cardTop}>
          <View>
            <Text style={type.label}>TO PIN</Text>
            <View style={styles.heroRow}>
              <Text style={styles.hero}>
                {located?.on_course
                  ? Math.round(located.to_middle_yards)
                  : recommendation
                    ? Math.round(recommendation.to_pin_yards)
                    : "—"}
              </Text>
              <Text style={styles.heroUnit}>YDS</Text>
            </View>
          </View>

          <View style={{ flex: 1 }} />

          {/*
            Only worth the space when conditions actually change the number. Comparing
            against the recommendation's own distance rather than the live one keeps both
            sides of the comparison from the same moment — otherwise walking makes them
            disagree and the card contradicts itself.
          */}
          {playsLikeDelta !== null ? (
            <View style={styles.playsLike}>
              <Text style={type.label}>PLAYS LIKE</Text>
              <Text style={type.bigNumber}>{Math.round(recommendation!.plays_like_yards)}</Text>
            </View>
          ) : null}
        </View>

        <View style={styles.divider} />

        <View style={styles.cardBottom}>
          <View style={styles.clubChip}>
            {thinking ? (
              <ActivityIndicator color={colors.onAccent} />
            ) : (
              <>
                <Text style={styles.clubText}>{recommendation?.best.club ?? "—"}</Text>
                <Text style={styles.clubLabel}>CLUB</Text>
              </>
            )}
          </View>

          <View style={{ flex: 1, gap: 7 }}>
            <Text style={type.subtitle} numberOfLines={1}>
              {recommendation ? aimSentence(recommendation.best.aim_description) : "Working it out…"}
            </Text>

            <OutcomeBar green={1 - trouble} safe={0} trouble={trouble} />

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chips}
            >
              {(recommendation?.hazards ?? []).map((h) => (
                <RiskChip key={h.lie} lie={h.lie} probability={h.probability} />
              ))}
              {recommendation && recommendation.hazards.length === 0 ? (
                <Text style={styles.clean}>NOTHING IN THE WAY</Text>
              ) : null}
            </ScrollView>
          </View>
        </View>
      </GlassPanel>

      <View style={[styles.actions, { bottom: insets.bottom + 20 }]}>
        <PrimaryButton label="LOG SHOT" style={{ flex: 1 }} icon={<Plus />} />
        <GhostButton label="TALK" accent style={{ width: 118 }} icon={<Mic />} />
      </View>
    </View>
  );
}

/** Front, middle, back — the three numbers a yardage book gives you. */
function GreenDistances({ located, top }: { located: Located; top: number }) {
  const rows: [string, number, boolean][] = [
    ["BACK", located.to_back_yards, false],
    ["MID", located.to_middle_yards, true],
    ["FRNT", located.to_front_yards, false],
  ];
  return (
    <View style={[styles.greenPanel, { top }]}>
      {rows.map(([label, yards, highlight]) => (
        <View key={label} style={styles.greenRow}>
          <Text style={styles.greenLabel}>{label}</Text>
          <Text style={[styles.greenValue, highlight && { color: colors.accent }]}>
            {Math.round(yards)}
          </Text>
        </View>
      ))}
    </View>
  );
}

/**
 * Whether the numbers can be trusted, stated plainly.
 *
 * A yardage from a 40-metre fix is worse than no yardage, because you'd act on it. So a
 * poor fix is flagged in red — the same colour as anything else that can cost you a shot.
 */
function GpsChip({
  gps,
  located,
  following,
  simulated,
  onResume,
}: {
  gps: ReturnType<typeof useLocation>;
  located: Located | null;
  following: boolean;
  simulated: boolean;
  onResume: () => void;
}) {
  const poorFix = gps.accuracyM !== null && gps.accuracyM > GOOD_ACCURACY_M;
  const offCourse = gps.status === "tracking" && located !== null && !located.on_course;

  let text: string;
  let tone: "good" | "bad" | "idle";

  if (simulated) {
    // Never dressed up as a real fix — the SIM tab beside this says where it came from.
    text = following ? "SIMULATED" : "TAP TO FOLLOW";
    tone = "idle";
  } else if (gps.status === "denied" || gps.status === "unavailable") {
    text = "NO GPS · FROM THE TEE";
    tone = "idle";
  } else if (gps.status === "starting") {
    text = "FINDING YOU…";
    tone = "idle";
  } else if (offCourse) {
    text = "NOT AT THE COURSE";
    tone = "idle";
  } else if (poorFix) {
    text = `WEAK FIX ±${Math.round(gps.accuracyM ?? 0)}M`;
    tone = "bad";
  } else if (!following) {
    text = "TAP TO FOLLOW GPS";
    tone = "idle";
  } else {
    text = "GPS";
    tone = "good";
  }

  const colour =
    tone === "good" ? colors.accent : tone === "bad" ? colors.signalSoft : colors.textMuted;
  const dot = tone === "good" ? colors.accent : tone === "bad" ? colors.signal : colors.textFaint;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={following ? "Following GPS" : "Resume following GPS"}
      onPress={onResume}
      style={[
        styles.gpsChip,
        tone === "bad" && { borderColor: glass.signalBorder, backgroundColor: glass.signalWash },
      ]}
    >
      <View style={[styles.gpsDot, { backgroundColor: dot }]} />
      <Text style={[styles.gpsText, { color: colour }]}>{text}</Text>
    </Pressable>
  );
}

/** "20 yds right" reads better as a sentence on the card. */
function aimSentence(description: string): string {
  if (description === "straight at it") return "Straight at the pin";
  return `Aim ${description}`;
}

function Chevron({ direction }: { direction: "left" | "right" }) {
  const d = direction === "left" ? "M15 18 L9 12 L15 6" : "M9 18 L15 12 L9 6";
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24">
      <Path d={d} stroke={colors.text} strokeWidth={2.2} strokeLinecap="round" fill="none" />
    </Svg>
  );
}

function Plus() {
  return (
    <Svg width={19} height={19} viewBox="0 0 24 24">
      <Path
        d="M12 5 L12 19 M5 12 L19 12"
        stroke={colors.onAccent}
        strokeWidth={2.4}
        strokeLinecap="round"
      />
    </Svg>
  );
}

function Mic() {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24">
      <Path
        d="M9 5 a3 3 0 0 1 6 0 v6 a3 3 0 0 1 -6 0 Z M5 11 a7 7 0 0 0 14 0 M12 18 L12 22"
        stroke={colors.accent}
        strokeWidth={2.2}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </Svg>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bgDeep },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    padding: 32,
    backgroundColor: colors.bgDeep,
  },
  errorTitle: { ...type.title, textAlign: "center" },
  errorBody: { ...type.body, color: colors.textMuted, textAlign: "center" },
  errorHint: { ...type.meta, color: colors.textFaint },

  header: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingHorizontal: 18,
    paddingBottom: 16,
    backgroundColor: "rgba(7,26,47,0.72)",
  },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 3, height: 3, borderRadius: 2, backgroundColor: "#45688A" },

  statusRow: {
    position: "absolute",
    right: 18,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  gpsChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: glass.borderSoft,
    backgroundColor: "rgba(12,39,64,0.8)",
  },
  gpsDot: { width: 6, height: 6, borderRadius: 3 },
  gpsText: { fontFamily: font.bodyBold, fontSize: 10, letterSpacing: 1.3 },

  greenPanel: {
    position: "absolute",
    left: 18,
    gap: 2,
    paddingHorizontal: 13,
    paddingVertical: 11,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: glass.borderSoft,
    backgroundColor: "rgba(12,39,64,0.8)",
  },
  greenRow: { flexDirection: "row", alignItems: "baseline", gap: 8 },
  greenLabel: {
    fontFamily: font.bodyBold,
    fontSize: 10,
    letterSpacing: 0.9,
    color: colors.textMuted,
    width: 36,
  },
  greenValue: {
    fontFamily: font.displaySemi,
    fontSize: 15,
    color: colors.text,
    fontVariant: ["tabular-nums"],
  },

  card: { position: "absolute", left: 14, right: 14, padding: 18, gap: 14 },
  cardTop: { flexDirection: "row", alignItems: "flex-end" },
  heroRow: { flexDirection: "row", alignItems: "baseline", gap: 6 },
  hero: { ...type.hero, fontVariant: ["tabular-nums"] },
  heroUnit: { fontFamily: font.bodyBold, fontSize: 13, letterSpacing: 1, color: colors.textMuted },
  playsLike: { alignItems: "flex-end", gap: 3, paddingBottom: 4 },

  divider: { height: 1, backgroundColor: "rgba(36,92,140,0.75)" },

  cardBottom: { flexDirection: "row", alignItems: "center", gap: 14 },
  clubChip: {
    width: 62,
    height: 62,
    borderRadius: radius.lg,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  clubText: { fontFamily: font.display, fontSize: 25, color: colors.onAccent },
  clubLabel: {
    fontFamily: font.bodyBold,
    fontSize: 8,
    letterSpacing: 1,
    color: colors.onAccentMuted,
  },
  chips: { gap: 8, paddingRight: 8 },
  clean: {
    fontFamily: font.bodyBold,
    fontSize: 10,
    letterSpacing: 1.2,
    color: colors.accent,
    paddingVertical: 6,
  },

  actions: { position: "absolute", left: 14, right: 14, flexDirection: "row", gap: 12 },
});

/**
 * The hole screen — the one you actually use on the course.
 *
 * Map-dominant on purpose: the course fills the screen and the numbers float over it, so
 * you read the shot spatially rather than as a table. Everything shown here comes from the
 * engine; nothing is invented on the client.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
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

import { api, ApiError, API_BASE_URL, type Course, type Recommendation } from "../src/api/client";
import { HoleMap } from "../src/components/HoleMap";
import { GhostButton, GlassPanel, IconButton, OutcomeBar, PrimaryButton, RiskChip } from "../src/components/ui";
import { colors, font, glass, radius, type } from "../src/theme";

const HANDICAP = 15;

export default function HoleScreen() {
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();

  const [course, setCourse] = useState<Course | null>(null);
  const [holeNumber, setHoleNumber] = useState(1);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);

  // Load whichever course has been imported. Course selection arrives with round setup.
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

  const loadRecommendation = useCallback(
    async (courseId: string, hole: number) => {
      setThinking(true);
      setError(null);
      try {
        const next = await api.recommend({
          course_id: courseId,
          hole,
          handicap: HANDICAP,
          samples: 2000,
        });
        setRecommendation(next);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
        setRecommendation(null);
      } finally {
        setThinking(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (course) loadRecommendation(course.course_id, holeNumber);
  }, [course, holeNumber, loadRecommendation]);

  const hole = course?.holes.find((h) => h.number === holeNumber) ?? null;
  const holeCount = course?.holes.length ?? 18;

  const trouble = (recommendation?.hazards ?? []).reduce((sum, h) => sum + h.probability, 0);

  // Keep the hole clear of the header and the card, so the ball is never hidden behind
  // the numbers describing the shot you're about to hit from it.
  const mapInset = useMemo(
    () => ({ top: insets.top + 84, bottom: insets.bottom + 300 }),
    [insets.top, insets.bottom],
  );

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
      <HoleMap
        hole={hole}
        recommendation={recommendation}
        width={width}
        height={height}
        inset={mapInset}
      />

      {/* header */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <IconButton
          label="Previous hole"
          onPress={() => setHoleNumber((n) => Math.max(1, n - 1))}
        >
          <Chevron direction="left" />
        </IconButton>

        <View style={{ flex: 1, gap: 3 }}>
          <Text style={type.title}>HOLE {hole.number}</Text>
          <View style={styles.metaRow}>
            <Text style={type.meta}>PAR {hole.par ?? "?"}</Text>
            <View style={styles.dot} />
            <Text style={type.meta}>{course.name.toUpperCase()}</Text>
          </View>
        </View>

        <IconButton
          label="Next hole"
          onPress={() => setHoleNumber((n) => Math.min(holeCount, n + 1))}
        >
          <Chevron direction="right" />
        </IconButton>
      </View>

      {/* the recommendation */}
      <GlassPanel style={[styles.card, { bottom: insets.bottom + 104 }]}>
        <View style={styles.cardTop}>
          <View>
            <Text style={type.label}>TO PIN</Text>
            <View style={styles.heroRow}>
              <Text style={styles.hero}>
                {recommendation ? Math.round(recommendation.to_pin_yards) : "—"}
              </Text>
              <Text style={styles.heroUnit}>YDS</Text>
            </View>
          </View>

          <View style={{ flex: 1 }} />

          {recommendation ? (
            <View style={styles.playsLike}>
              <Text style={type.label}>PLAYS LIKE</Text>
              <Text style={type.bigNumber}>{Math.round(recommendation.plays_like_yards)}</Text>
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

            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
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

      {/* actions */}
      <View style={[styles.actions, { bottom: insets.bottom + 20 }]}>
        <PrimaryButton label="LOG SHOT" style={{ flex: 1 }} icon={<Plus />} />
        <GhostButton label="TALK" accent style={{ width: 118 }} icon={<Mic />} />
      </View>
    </View>
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

  card: {
    position: "absolute",
    left: 14,
    right: 14,
    padding: 18,
    gap: 14,
  },
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

  actions: {
    position: "absolute",
    left: 14,
    right: 14,
    flexDirection: "row",
    gap: 12,
  },
});

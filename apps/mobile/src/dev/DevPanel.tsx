/**
 * Stand anywhere on the course without leaving your desk. Development only.
 *
 * This does not fake distances or shortcut the engine. It asks the server for a real
 * lat/lon on a chosen hole and hands it to the app as if the phone's GPS had reported it,
 * so everything downstream — hole detection, yardages, re-simulation, the dispersion cone —
 * runs exactly as it does on the course. Testing through here tests the real thing.
 *
 * Gated behind __DEV__, so it cannot reach a release build.
 */

import { useCallback, useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api/client";
import { colors, font, glass, radius, type } from "../theme";

export type SimulatedFix = { latitude: number; longitude: number } | null;

/** How fast a golfer walks, roughly, in yards per tick. */
const WALK_YARDS_PER_TICK = 8;
const WALK_TICK_MS = 1500;

export function DevPanel({
  courseId,
  holeCount,
  onFix,
  onClear,
  active,
}: {
  courseId: string;
  holeCount: number;
  onFix: (fix: SimulatedFix) => void;
  onClear: () => void;
  active: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [hole, setHole] = useState(11);
  const [fromYards, setFromYards] = useState(150);
  const [offsetYards, setOffsetYards] = useState(0);
  const [walking, setWalking] = useState(false);

  const push = useCallback(
    async (h: number, yards: number, offset: number) => {
      try {
        const { lat, lon } = await api.devPosition(courseId, h, Math.max(yards, 1), offset);
        onFix({ latitude: lat, longitude: lon });
      } catch {
        // The panel is a convenience; a failure here should never take the screen down.
      }
    },
    [courseId, onFix],
  );

  // Re-place the player whenever the knobs move. Opening the panel is itself enough to
  // take over — waiting for the simulation to already be active would mean it could never
  // start, since starting it is what this does.
  useEffect(() => {
    if (open || active) push(hole, fromYards, offsetYards);
  }, [open, active, hole, fromYards, offsetYards, push]);

  // Walking in: the point of this is to watch the yardage tick down the way it will on
  // the course, rather than jump between two static positions.
  useEffect(() => {
    if (!walking) return;
    const timer = setInterval(() => {
      setFromYards((y) => {
        const next = y - WALK_YARDS_PER_TICK;
        if (next <= 5) {
          setWalking(false);
          return 5;
        }
        return next;
      });
    }, WALK_TICK_MS);
    return () => clearInterval(timer);
  }, [walking]);

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Simulated position controls"
        onPress={() => setOpen(true)}
        style={[styles.tab, active && styles.tabActive]}
      >
        <Text style={[styles.tabText, active && { color: colors.onAccent }]}>
          {active ? `SIM · H${hole} · ${Math.round(fromYards)}Y` : "SIM"}
        </Text>
      </Pressable>

      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <View style={styles.backdrop}>
          <View style={styles.sheet}>
            <View style={styles.grabber} />

            <View style={styles.titleRow}>
              <Text style={type.title}>Simulated position</Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Close"
                onPress={() => setOpen(false)}
                style={styles.close}
              >
                <Text style={styles.closeText}>✕</Text>
              </Pressable>
            </View>

            <Text style={styles.explainer}>
              Feeds the app a real coordinate on the course, as if it came from GPS. Everything
              downstream behaves exactly as it will on the course.
            </Text>

            <Stepper
              label="HOLE"
              value={String(hole)}
              onDown={() => setHole((h) => Math.max(1, h - 1))}
              onUp={() => setHole((h) => Math.min(holeCount, h + 1))}
            />

            <Stepper
              label="FROM PIN"
              value={`${Math.round(fromYards)} yds`}
              onDown={() => setFromYards((y) => Math.max(5, y - 10))}
              onUp={() => setFromYards((y) => Math.min(600, y + 10))}
            />

            <View style={styles.group}>
              <Text style={type.label}>OFF THE LINE</Text>
              <View style={styles.chipRow}>
                {[-30, -15, 0, 15, 30].map((value) => (
                  <Pressable
                    key={value}
                    accessibilityRole="button"
                    onPress={() => setOffsetYards(value)}
                    style={[styles.chip, offsetYards === value && styles.chipOn]}
                  >
                    <Text
                      style={[styles.chipText, offsetYards === value && { color: colors.onAccent }]}
                    >
                      {value === 0 ? "CENTRE" : `${Math.abs(value)}${value < 0 ? "L" : "R"}`}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>

            <View style={styles.group}>
              <Text style={type.label}>QUICK JUMPS</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={styles.chipRow}>
                  {[
                    ["TEE", 420],
                    ["LAYUP", 250],
                    ["APPROACH", 150],
                    ["PITCH", 60],
                    ["CHIP", 20],
                  ].map(([label, yards]) => (
                    <Pressable
                      key={label as string}
                      accessibilityRole="button"
                      onPress={() => setFromYards(yards as number)}
                      style={styles.chip}
                    >
                      <Text style={styles.chipText}>{label}</Text>
                    </Pressable>
                  ))}
                </View>
              </ScrollView>
            </View>

            <View style={styles.actions}>
              <Pressable
                accessibilityRole="button"
                onPress={() => setWalking((w) => !w)}
                style={[styles.action, walking && styles.actionOn]}
              >
                <Text style={[styles.actionText, walking && { color: colors.onAccent }]}>
                  {walking ? "STOP" : "WALK IN"}
                </Text>
              </Pressable>

              <Pressable
                accessibilityRole="button"
                onPress={() => {
                  setWalking(false);
                  onClear();
                  setOpen(false);
                }}
                style={styles.action}
              >
                <Text style={styles.actionText}>USE REAL GPS</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

function Stepper({
  label,
  value,
  onDown,
  onUp,
}: {
  label: string;
  value: string;
  onDown: () => void;
  onUp: () => void;
}) {
  return (
    <View style={styles.group}>
      <Text style={type.label}>{label}</Text>
      <View style={styles.stepperRow}>
        <Pressable accessibilityRole="button" accessibilityLabel={`${label} down`} onPress={onDown} style={styles.step}>
          <Text style={styles.stepText}>−</Text>
        </Pressable>
        <Text style={styles.stepValue}>{value}</Text>
        <Pressable accessibilityRole="button" accessibilityLabel={`${label} up`} onPress={onUp} style={styles.step}>
          <Text style={styles.stepText}>+</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  tab: {
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: glass.borderSoft,
    backgroundColor: "rgba(12,39,64,0.85)",
  },
  tabActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  tabText: { fontFamily: font.bodyBold, fontSize: 10, letterSpacing: 1.2, color: colors.textMuted },

  backdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(7,26,47,0.75)" },
  sheet: {
    padding: 20,
    paddingBottom: 38,
    gap: 16,
    borderTopLeftRadius: 30,
    borderTopRightRadius: 30,
    borderTopWidth: 1,
    borderColor: glass.border,
    backgroundColor: colors.bg,
  },
  grabber: {
    width: 44,
    height: 4,
    borderRadius: 2,
    alignSelf: "center",
    backgroundColor: glass.border,
  },
  titleRow: { flexDirection: "row", alignItems: "center" },
  close: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: "auto",
  },
  closeText: { color: colors.textMuted, fontSize: 18 },
  explainer: { ...type.body, fontSize: 13, color: colors.textMuted },

  group: { gap: 9 },
  stepperRow: { flexDirection: "row", alignItems: "center", gap: 14 },
  step: {
    width: 52,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: glass.border,
    backgroundColor: glass.raised,
  },
  stepText: { fontFamily: font.display, fontSize: 22, color: colors.text },
  stepValue: {
    flex: 1,
    textAlign: "center",
    fontFamily: font.display,
    fontSize: 22,
    color: colors.accent,
    fontVariant: ["tabular-nums"],
  },

  chipRow: { flexDirection: "row", gap: 8 },
  chip: {
    paddingHorizontal: 13,
    height: 40,
    justifyContent: "center",
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: glass.border,
    backgroundColor: glass.raised,
  },
  chipOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { fontFamily: font.bodyBold, fontSize: 11, letterSpacing: 0.8, color: colors.textMuted },

  actions: { flexDirection: "row", gap: 10, paddingTop: 4 },
  action: {
    flex: 1,
    height: 54,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: glass.border,
    backgroundColor: glass.raised,
  },
  actionOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  actionText: { fontFamily: font.display, fontSize: 14, letterSpacing: 0.8, color: colors.text },
});

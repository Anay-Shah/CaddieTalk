/**
 * The small pieces every screen shares.
 *
 * The rule these encode: butter is the only colour you tap, and red only ever means danger
 * or a live microphone. Keeping that in components rather than in everyone's memory is
 * what stops it drifting.
 */

import React from "react";
import { Pressable, StyleSheet, Text, View, type ViewStyle } from "react-native";

import { colors, font, glass, HIT_SIZE, radius, type } from "../theme";

export function Label({ children, style }: { children: React.ReactNode; style?: object }) {
  return <Text style={[type.label, style]}>{children}</Text>;
}

/** A floating marine panel. Everything that sits over the course uses this. */
export function GlassPanel({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: ViewStyle | ViewStyle[];
}) {
  return <View style={[styles.glass, style]}>{children}</View>;
}

export function PrimaryButton({
  label,
  onPress,
  icon,
  style,
}: {
  label: string;
  onPress?: () => void;
  icon?: React.ReactNode;
  style?: ViewStyle;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.primary,
        pressed && { backgroundColor: colors.accentDeep },
        style,
      ]}
    >
      {icon}
      <Text style={[type.button, { color: colors.onAccent }]}>{label}</Text>
    </Pressable>
  );
}

export function GhostButton({
  label,
  onPress,
  icon,
  accent = false,
  style,
}: {
  label: string;
  onPress?: () => void;
  icon?: React.ReactNode;
  /** Butter outline rather than marine — for a secondary action, not a destructive one. */
  accent?: boolean;
  style?: ViewStyle;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.ghost,
        { borderColor: accent ? glass.accentBorder : glass.border },
        pressed && { backgroundColor: glass.raised },
        style,
      ]}
    >
      {icon}
      <Text style={[type.button, { color: accent ? colors.accent : colors.textMuted }]}>
        {label}
      </Text>
    </Pressable>
  );
}

/** A risk readout. Always red, because it is always something that can go wrong. */
export function RiskChip({ lie, probability }: { lie: string; probability: number }) {
  return (
    <View style={styles.riskChip}>
      <View style={styles.riskDot} />
      <Text style={styles.riskText}>
        {lie.toUpperCase()} {Math.round(probability * 100)}%
      </Text>
    </View>
  );
}

/**
 * Where this club finishes, as one bar.
 *
 * Butter for the green, muted marine for everything survivable, red for trouble — so the
 * shape of the bar tells you the risk before you read any number.
 */
export function OutcomeBar({
  green,
  safe,
  trouble,
}: {
  green: number;
  safe: number;
  trouble: number;
}) {
  const total = Math.max(green + safe + trouble, 0.0001);
  return (
    <View style={styles.bar}>
      <View style={{ flex: green / total, backgroundColor: colors.accent }} />
      <View style={{ flex: safe / total, backgroundColor: "#6E8FA8" }} />
      <View style={{ flex: trouble / total, backgroundColor: colors.signal }} />
    </View>
  );
}

export function IconButton({
  onPress,
  label,
  children,
}: {
  onPress?: () => void;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [styles.iconButton, pressed && { backgroundColor: glass.border }]}
    >
      {children}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  glass: {
    backgroundColor: glass.panel,
    borderRadius: radius.xxl,
    borderWidth: 1,
    borderColor: glass.border,
  },
  primary: {
    height: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    borderRadius: radius.xl,
    backgroundColor: colors.accent,
  },
  ghost: {
    height: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
    borderRadius: radius.xl,
    borderWidth: 1,
    backgroundColor: "rgba(19,56,90,0.7)",
  },
  iconButton: {
    width: HIT_SIZE,
    height: HIT_SIZE,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: glass.borderSoft,
    backgroundColor: glass.raised,
  },
  riskChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 11,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: glass.signalBorder,
    backgroundColor: glass.signalWash,
  },
  riskDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.signal,
  },
  riskText: {
    fontFamily: font.bodyBold,
    fontSize: 10,
    letterSpacing: 1.2,
    color: colors.signalSoft,
  },
  bar: {
    flexDirection: "row",
    height: 7,
    borderRadius: 4,
    overflow: "hidden",
    backgroundColor: "rgba(36,92,140,0.5)",
  },
});

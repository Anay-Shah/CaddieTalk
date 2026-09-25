/**
 * The CaddieTalk design system.
 *
 * Three colours, each with exactly one job:
 *   marine  — surfaces and chrome, the ground everything sits on
 *   butter  — the play: anything you tap, the aim line, the recommendation
 *   signal  — danger and live: hazards, risk, and a hot microphone
 *
 * Red never labels an action. If it is red, it is either something that can go
 * wrong or a microphone that is listening. That rule is what keeps the screen
 * readable at a glance with a club in your other hand.
 */

export const colors = {
  /** Deep marine — the base the whole app sits on. */
  bgDeep: "#071A2F",
  /** Marine — screens and glass panels over the course. */
  bg: "#0C2740",
  /** Raised marine — cards and pressed states. */
  surface: "#13385A",
  /** Hairlines and borders. */
  line: "#245C8C",

  /** Butter yellow — the play. The only colour you tap. */
  accent: "#F5DE8B",
  /** Butter, pressed. */
  accentDeep: "#E8C960",
  /** Ink on a butter surface. */
  onAccent: "#071A2F",
  /** Small text on butter, where full contrast would shout. */
  onAccentMuted: "#6B5A1E",

  /** Signal red — danger, and a live microphone. Never an action. */
  signal: "#FF3B30",
  /** Signal red lightened for small text, which needs more contrast on marine. */
  signalSoft: "#FF8A80",

  text: "#F7F4EA",
  textMuted: "#93B0C9",
  textFaint: "#6E8FA8",

  /** The course itself, drawn from imported geometry. */
  course: {
    rough: "#16311F",
    roughDark: "#1E3A28",
    fairway: "#2C5741",
    green: "#3F8257",
    greenEdge: "#54A06D",
    sand: "#C9B27C",
    water: "#1E4A6B",
    waterEdge: "#2E6C96",
  },
} as const;

/** Translucent fills, for panels that float over the course. */
export const glass = {
  panel: "rgba(12,39,64,0.93)",
  raised: "rgba(19,56,90,0.55)",
  border: "rgba(36,92,140,0.8)",
  borderSoft: "rgba(36,92,140,0.6)",
  accentBorder: "rgba(245,222,139,0.55)",
  accentWash: "rgba(245,222,139,0.10)",
  signalWash: "rgba(255,59,48,0.13)",
  signalBorder: "rgba(255,59,48,0.45)",
} as const;

export const font = {
  /** Numbers and headings. Tabular figures so yardages don't jitter as they tick. */
  display: "SpaceGrotesk_700Bold",
  displayMedium: "SpaceGrotesk_500Medium",
  displaySemi: "SpaceGrotesk_600SemiBold",
  /** Anything read as a sentence. */
  body: "Manrope_400Regular",
  bodyMedium: "Manrope_500Medium",
  bodySemi: "Manrope_600SemiBold",
  bodyBold: "Manrope_700Bold",
} as const;

export const radius = {
  sm: 9,
  md: 14,
  lg: 18,
  xl: 22,
  xxl: 26,
  pill: 999,
} as const;

export const space = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 18,
  xl: 24,
  xxl: 32,
} as const;

/** Anything tappable is at least this tall — you are wearing a glove. */
export const HIT_SIZE = 44;

export const type = {
  /** The hero yardage. */
  hero: {
    fontFamily: font.display,
    fontSize: 56,
    lineHeight: 52,
    letterSpacing: -1,
    color: colors.text,
  },
  bigNumber: {
    fontFamily: font.display,
    fontSize: 30,
    lineHeight: 32,
    color: colors.accent,
  },
  title: {
    fontFamily: font.display,
    fontSize: 21,
    color: colors.text,
  },
  subtitle: {
    fontFamily: font.displaySemi,
    fontSize: 17,
    color: colors.text,
  },
  body: {
    fontFamily: font.body,
    fontSize: 15,
    lineHeight: 22,
    color: colors.text,
  },
  /** Small all-caps labels. Letter-spaced so they read as labels, not copy. */
  label: {
    fontFamily: font.bodyBold,
    fontSize: 10,
    letterSpacing: 1.6,
    color: colors.textMuted,
  },
  meta: {
    fontFamily: font.bodySemi,
    fontSize: 12,
    letterSpacing: 1.4,
    color: colors.textMuted,
  },
  button: {
    fontFamily: font.display,
    fontSize: 16,
    letterSpacing: 1,
  },
} as const;

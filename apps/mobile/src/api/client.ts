/**
 * Talking to the CaddieTalk backend.
 *
 * During development that backend is a Python server on the builder's laptop, reached over
 * wifi. Everything goes through one configurable base URL so that pointing the app at a
 * deployed backend later is a config change rather than a rewrite — see DECISIONS.md
 * (D-008).
 */

import Constants from "expo-constants";

/**
 * Where the dev server lives.
 *
 * Expo tells us the host machine's LAN address, which is the same machine running the
 * Python server, so a phone on the same wifi can find it without anything hard-coded.
 */
function inferDevHost(): string {
  const hostUri = Constants.expoConfig?.hostUri;
  const host = typeof hostUri === "string" ? hostUri.split(":")[0] : undefined;
  return host ? `http://${host}:8000` : "http://localhost:8000";
}

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? inferDevHost();

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(
      `Can't reach the caddie server at ${API_BASE_URL}. Is it running, and is this device on the same wifi?`,
    );
  }

  if (!response.ok) {
    throw new ApiError(`${init?.method ?? "GET"} ${path} failed`, response.status);
  }
  return (await response.json()) as T;
}

// --- shapes the server returns -------------------------------------------------------

export type CourseSummary = {
  course_id: string;
  name: string;
  holes: number;
};

export type TeeBox = { name: string | null; polygon: number[][] };

export type Hole = {
  number: number;
  par: number | null;
  hole_line: number[][];
  tees: TeeBox[];
  green: number[][] | null;
  fairways: number[][][];
  bunkers: number[][][];
  water: number[][][];
  trees: number[][][];
};

export type Course = {
  course_id: string;
  name: string;
  crs: string;
  bbox_lonlat: number[];
  holes: Hole[];
};

export type Candidate = {
  club: string;
  aim_offset_yards: number;
  aim_description: string;
  expected_score: number;
};

export type Recommendation = {
  hole: number;
  par: number | null;
  to_pin_yards: number;
  plays_like_yards: number;
  lie: string;
  best: Candidate;
  alternatives: Candidate[];
  hazards: { lie: string; probability: number }[];
  aim_xy: [number, number];
  pin_xy: [number, number];
  start_xy: [number, number];
  /** A thinned sample of simulated landings, for drawing the dispersion cone. */
  landing_sample: [number, number][];
};

export type RecommendInput = {
  course_id: string;
  hole: number;
  start?: [number, number];
  from_yards?: number;
  lie?: string;
  handicap?: number;
  wind_mph?: number;
  wind_bearing_deg?: number;
  elevation_yards?: number;
  samples?: number;
  seed?: number;
};

// --- endpoints -----------------------------------------------------------------------

export const api = {
  health: () => request<{ status: string }>("/health"),

  courses: () => request<CourseSummary[]>("/courses"),

  course: (courseId: string) => request<Course>(`/courses/${courseId}`),

  recommend: (input: RecommendInput) =>
    request<Recommendation>("/engine/recommend", {
      method: "POST",
      body: JSON.stringify(input),
    }),
};

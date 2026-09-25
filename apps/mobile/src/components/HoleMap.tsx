/**
 * The hole, drawn from imported OpenStreetMap geometry, with the dispersion cone on top.
 *
 * Two things make this readable on a phone at arm's length:
 *
 * 1. The whole scene is ROTATED so the shot you are about to hit points up the screen.
 *    Golfers orient themselves to the shot, not to north.
 * 2. It is framed on the ball and the target, not on the whole hole, so the part you are
 *    playing fills the view.
 *
 * The cone is the signature element: an ellipse fitted to the simulated landings, so it
 * shows where this club actually finishes for this player rather than a generic target
 * ring. Where it crosses a bunker or water, that hazard is tinted red.
 */

import React, { useMemo } from "react";
import Svg, {
  Circle,
  ClipPath,
  Defs,
  Ellipse,
  G,
  Line,
  Path,
  RadialGradient,
  Rect,
  Stop,
} from "react-native-svg";

import type { Hole, Recommendation } from "../api/client";
import { colors } from "../theme";

type Point = [number, number];

type Props = {
  hole: Hole;
  recommendation: Recommendation | null;
  width: number;
  height: number;
  /**
   * Space taken by the floating panels. The hole is fitted into what's left, so the ball
   * and the green are never hidden behind the header or the recommendation card.
   */
  inset?: { top: number; bottom: number };
};

const PADDING_X = 26;
/** Keeps the ball and the pin off the very edge of the band the panels leave. */
const PADDING_Y = 24;

function centroid(ring: number[][]): Point {
  let x = 0;
  let y = 0;
  for (const [px, py] of ring) {
    x += px;
    y += py;
  }
  return [x / ring.length, y / ring.length];
}

/**
 * Builds a function mapping course metres to screen pixels.
 *
 * Rotating first and fitting second is what keeps the shot vertical while still filling
 * the available space.
 */
function makeProjection(
  origin: Point,
  target: Point,
  points: Point[],
  width: number,
  height: number,
  inset: { top: number; bottom: number },
) {
  // Bearing is measured clockwise from north, the engine's convention. Rotating the scene
  // by +bearing (counterclockwise) is what swings the target onto the +y axis, so the shot
  // you are about to hit points up the screen.
  const bearing = Math.atan2(target[0] - origin[0], target[1] - origin[1]);
  const sin = Math.sin(bearing);
  const cos = Math.cos(bearing);

  const rotate = ([x, y]: Point): Point => {
    const dx = x - origin[0];
    const dy = y - origin[1];
    return [dx * cos - dy * sin, dx * sin + dy * cos];
  };

  const rotated = points.map(rotate);
  const xs = rotated.map((p) => p[0]);
  const ys = rotated.map((p) => p[1]);

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);

  // The usable band is what the floating panels leave behind.
  const usableHeight = Math.max(height - inset.top - inset.bottom - PADDING_Y * 2, 80);
  const scale = Math.min((width - PADDING_X * 2) / spanX, usableHeight / spanY);

  const offsetX = (width - spanX * scale) / 2;
  const offsetY = inset.top + PADDING_Y + (usableHeight - spanY * scale) / 2;

  return {
    scale,
    project: (point: Point): Point => {
      const [rx, ry] = rotate(point);
      return [
        offsetX + (rx - minX) * scale,
        // SVG y grows downward, so the far end of the hole has to land at the top.
        offsetY + (maxY - ry) * scale,
      ];
    },
  };
}

function ringToPath(ring: number[][], project: (p: Point) => Point): string {
  if (ring.length < 3) return "";
  return (
    ring
      .map(([x, y], index) => {
        const [sx, sy] = project([x, y]);
        return `${index === 0 ? "M" : "L"} ${sx.toFixed(1)} ${sy.toFixed(1)}`;
      })
      .join(" ") + " Z"
  );
}

/** Mean and spread of the landings, in screen space, for the cone. */
function fitCone(landings: Point[], project: (p: Point) => Point) {
  if (landings.length < 8) return null;

  const screen = landings.map(project);
  const meanX = screen.reduce((sum, p) => sum + p[0], 0) / screen.length;
  const meanY = screen.reduce((sum, p) => sum + p[1], 0) / screen.length;

  const varX = screen.reduce((sum, p) => sum + (p[0] - meanX) ** 2, 0) / screen.length;
  const varY = screen.reduce((sum, p) => sum + (p[1] - meanY) ** 2, 0) / screen.length;

  // Two standard deviations covers ~95% of shots, which is the honest envelope to draw:
  // wide enough to include the misses that actually matter for strategy.
  return {
    cx: meanX,
    cy: meanY,
    rx: Math.max(Math.sqrt(varX) * 2, 6),
    ry: Math.max(Math.sqrt(varY) * 2, 6),
  };
}

export function HoleMap({
  hole,
  recommendation,
  width,
  height,
  inset = { top: 0, bottom: 0 },
}: Props) {
  const scene = useMemo(() => {
    const teeXy = (hole.hole_line[0] ?? [0, 0]) as Point;
    const greenXy = hole.green
      ? centroid(hole.green)
      : ((hole.hole_line[hole.hole_line.length - 1] ?? [0, 1]) as Point);

    const origin = (recommendation?.start_xy ?? teeXy) as Point;
    const target = (recommendation?.pin_xy ?? greenXy) as Point;
    const landings = (recommendation?.landing_sample ?? []) as Point[];

    // Frame on what is in play: the ball, the target, the green, and where shots land.
    const framing: Point[] = [
      origin,
      target,
      ...(hole.green ?? []).map((p) => p as Point),
      ...landings,
    ];

    const { project } = makeProjection(origin, target, framing, width, height, inset);

    return {
      project,
      origin,
      target,
      ballAt: project(origin),
      pinAt: project(target),
      aimAt: recommendation ? project(recommendation.aim_xy as Point) : null,
      cone: fitCone(landings, project),
      fairways: hole.fairways.map((r) => ringToPath(r, project)),
      trees: hole.trees.map((r) => ringToPath(r, project)),
      water: hole.water.map((r) => ringToPath(r, project)),
      bunkers: hole.bunkers.map((r) => ringToPath(r, project)),
      green: hole.green ? ringToPath(hole.green, project) : null,
    };
  }, [hole, recommendation, width, height, inset]);

  const { cone } = scene;

  return (
    <Svg width={width} height={height}>
      <Defs>
        <RadialGradient id="coneFill" cx="50%" cy="50%" r="50%">
          <Stop offset="0%" stopColor={colors.accent} stopOpacity={0.6} />
          <Stop offset="52%" stopColor={colors.accent} stopOpacity={0.26} />
          <Stop offset="100%" stopColor={colors.accent} stopOpacity={0} />
        </RadialGradient>
        {cone ? (
          <ClipPath id="coneClip">
            <Ellipse cx={cone.cx} cy={cone.cy} rx={cone.rx} ry={cone.ry} />
          </ClipPath>
        ) : null}
      </Defs>

      <Rect x={0} y={0} width={width} height={height} fill={colors.course.rough} />

      {scene.trees.map((d, i) => (
        <Path key={`t${i}`} d={d} fill={colors.course.roughDark} />
      ))}
      {scene.fairways.map((d, i) => (
        <Path key={`f${i}`} d={d} fill={colors.course.fairway} />
      ))}
      {scene.water.map((d, i) => (
        <Path
          key={`w${i}`}
          d={d}
          fill={colors.course.water}
          stroke={colors.course.waterEdge}
          strokeWidth={1.5}
        />
      ))}
      {scene.green ? (
        <Path
          d={scene.green}
          fill={colors.course.green}
          stroke={colors.course.greenEdge}
          strokeWidth={1.5}
        />
      ) : null}
      {scene.bunkers.map((d, i) => (
        <Path key={`b${i}`} d={d} fill={colors.course.sand} />
      ))}

      {/* where this club actually finishes */}
      {cone ? (
        <G>
          <Ellipse cx={cone.cx} cy={cone.cy} rx={cone.rx} ry={cone.ry} fill="url(#coneFill)" />
          <Ellipse
            cx={cone.cx}
            cy={cone.cy}
            rx={cone.rx}
            ry={cone.ry}
            fill="none"
            stroke={colors.accent}
            strokeOpacity={0.45}
            strokeWidth={1.5}
            strokeDasharray="3 5"
          />

          {/* the slice of each hazard the cone reaches */}
          <G clipPath="url(#coneClip)">
            {scene.bunkers.map((d, i) => (
              <Path key={`bh${i}`} d={d} fill={colors.signal} fillOpacity={0.75} />
            ))}
            {scene.water.map((d, i) => (
              <Path key={`wh${i}`} d={d} fill={colors.signal} fillOpacity={0.75} />
            ))}
          </G>
        </G>
      ) : null}

      {/* aim line */}
      {scene.aimAt ? (
        <G>
          <Line
            x1={scene.ballAt[0]}
            y1={scene.ballAt[1]}
            x2={scene.aimAt[0]}
            y2={scene.aimAt[1]}
            stroke={colors.accent}
            strokeWidth={2}
            strokeDasharray="7 7"
            strokeOpacity={0.9}
          />
          <Circle
            cx={scene.aimAt[0]}
            cy={scene.aimAt[1]}
            r={7}
            fill="none"
            stroke={colors.accent}
            strokeWidth={2}
          />
          <Circle cx={scene.aimAt[0]} cy={scene.aimAt[1]} r={2.5} fill={colors.accent} />
        </G>
      ) : null}

      {/* pin */}
      <G>
        <Line
          x1={scene.pinAt[0]}
          y1={scene.pinAt[1]}
          x2={scene.pinAt[0]}
          y2={scene.pinAt[1] - 24}
          stroke={colors.text}
          strokeWidth={2}
        />
        <Path
          d={`M ${scene.pinAt[0]} ${scene.pinAt[1] - 24} L ${scene.pinAt[0] + 15} ${
            scene.pinAt[1] - 18
          } L ${scene.pinAt[0]} ${scene.pinAt[1] - 12} Z`}
          fill={colors.signal}
        />
        <Circle cx={scene.pinAt[0]} cy={scene.pinAt[1]} r={3} fill={colors.text} />
      </G>

      {/* the ball */}
      <G>
        <Circle
          cx={scene.ballAt[0]}
          cy={scene.ballAt[1]}
          r={13}
          fill={colors.accent}
          fillOpacity={0.16}
        />
        <Circle
          cx={scene.ballAt[0]}
          cy={scene.ballAt[1]}
          r={6}
          fill={colors.accent}
          stroke={colors.bgDeep}
          strokeWidth={1.5}
        />
      </G>
    </Svg>
  );
}

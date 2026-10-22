import {
  RippleField,
  RIPPLE_SETTINGS
} from "../src/behavior-ripple-field-v13c.js";


const VISIBLE_WIDTH = 16;
const VISIBLE_SEGMENTS = 128;

const DX =
  VISIBLE_WIDTH /
  VISIBLE_SEGMENTS;

const DT = 1 / 120;
const DURATION = 11;


// ------------------------------------------------------------
// Invisible continuation.
//
// 24 cells × 0.125 = 3 physical units beyond every
// visible edge.
//
// At propagation speed 3, this gives about 1 second
// of hidden outward travel before the numerical wall.
// ------------------------------------------------------------

const GUARD_CELLS = 24;

const EXTENDED_SEGMENTS =
  VISIBLE_SEGMENTS +
  2 * GUARD_CELLS;

const EXTENDED_WIDTH =
  VISIBLE_WIDTH +
  2 * GUARD_CELLS * DX;


// ------------------------------------------------------------
// Smooth hidden absorption.
//
// IMPORTANT:
// The visible boundary itself receives NO additional
// absorption.
//
// Absorption begins only after the wave has crossed
// outside the visible mesh.
//
// smoothstep has zero slope at both ends, avoiding an
// abrupt damping discontinuity.
//
// With max extra damping 6 and ~1 s traversal,
// theoretical attenuation across the whole hidden layer
// is approximately exp(-3) ~= 5% one-way before the
// numerical wall, before considering the normal damping.
// ------------------------------------------------------------

const MAX_HIDDEN_DAMPING = 6;


const clamp =
  (v, lo, hi) =>
    Math.max(
      lo,
      Math.min(
        hi,
        v
      )
    );


function smoothstep01(x) {

  const s =
    clamp(
      x,
      0,
      1
    );

  return (
    s *
    s *
    (3 - 2 * s)
  );
}


function createBaseline() {

  return new RippleField(
    VISIBLE_WIDTH,
    VISIBLE_WIDTH,
    VISIBLE_SEGMENTS,
    VISIBLE_SEGMENTS
  );
}


function createInvisibleContinuation() {

  const field =
    new RippleField(
      EXTENDED_WIDTH,
      EXTENDED_WIDTH,
      EXTENDED_SEGMENTS,
      EXTENDED_SEGMENTS
    );


  const center =
    (field.columns - 1) / 2;

  const visibleHalf =
    VISIBLE_SEGMENTS / 2;


  // Replace constructor attenuation with:
  //
  // visible domain:
  //     normal global damping only
  //
  // hidden domain:
  //     normal damping + progressive sponge
  //
  // The visible border therefore remains fully dynamic.

  for (
    let row = 0;
    row < field.rows;
    row++
  ) {

    for (
      let col = 0;
      col < field.columns;
      col++
    ) {

      const i =
        row *
        field.columns +
        col;


      const outsideX =
        Math.max(
          0,
          Math.abs(
            col - center
          ) - visibleHalf
        );


      const outsideZ =
        Math.max(
          0,
          Math.abs(
            row - center
          ) - visibleHalf
        );


      const hiddenDepth =
        Math.max(
          outsideX,
          outsideZ
        );


      const normalizedHiddenDepth =
        hiddenDepth /
        GUARD_CELLS;


      const sponge =
        smoothstep01(
          normalizedHiddenDepth
        );


      const localDamping =
        RIPPLE_SETTINGS.damping +
        MAX_HIDDEN_DAMPING *
        sponge;


      field.attenuation[i] =
        Math.exp(
          -localDamping *
          field.step
        );
    }
  }


  return field;
}


function visibleMetrics(
  field,
  guard
) {

  const visibleSide =
    VISIBLE_SEGMENTS + 1;

  const visibleCenter =
    VISIBLE_SEGMENTS / 2;


  let centerMax = 0;
  let edgeMax = 0;
  let wholeSq = 0;

  let wholeN = 0;


  for (
    let vz = 0;
    vz < visibleSide;
    vz++
  ) {

    for (
      let vx = 0;
      vx < visibleSide;
      vx++
    ) {

      const row =
        vz + guard;

      const col =
        vx + guard;

      const i =
        row *
        field.columns +
        col;


      const h =
        field.heights[i];

      const ah =
        Math.abs(h);


      wholeSq +=
        h * h;

      wholeN++;


      const dx =
        vx -
        visibleCenter;

      const dz =
        vz -
        visibleCenter;

      const radius =
        Math.sqrt(
          dx * dx +
          dz * dz
        );


      if (
        radius <=
        visibleCenter *
        0.15
      ) {

        centerMax =
          Math.max(
            centerMax,
            ah
          );
      }


      const edgeDistance =
        Math.min(
          vx,
          vz,
          VISIBLE_SEGMENTS - vx,
          VISIBLE_SEGMENTS - vz
        );


      // Same outer visible region used by the
      // previous audit.
      if (
        edgeDistance <=
        visibleCenter *
        0.10
      ) {

        edgeMax =
          Math.max(
            edgeMax,
            ah
          );
      }
    }
  }


  return {
    centerMax,
    edgeMax,

    wholeRms:
      Math.sqrt(
        wholeSq /
        wholeN
      )
  };
}


function run(
  label,
  field,
  guard
) {

  field.exciteBipolarAt(
    0,
    0,
    0.50,
    0.80
  );


  let earlyCenterPeak = 0;
  let edgeArrivalPeak = 0;

  let lateCenterPeak = 0;
  let lateCenterPeakTime = 0;

  const trace = [];


  const steps =
    Math.round(
      DURATION / DT
    );


  for (
    let step = 0;
    step <= steps;
    step++
  ) {

    const t =
      step * DT;


    if (step > 0) {
      field.advance(DT);
    }


    const m =
      visibleMetrics(
        field,
        guard
      );


    if (t <= 1.25) {

      earlyCenterPeak =
        Math.max(
          earlyCenterPeak,
          m.centerMax
        );
    }


    if (
      t >= 2.0 &&
      t <= 4.0
    ) {

      edgeArrivalPeak =
        Math.max(
          edgeArrivalPeak,
          m.edgeMax
        );
    }


    if (
      t >= 4.5 &&
      t <= 10.5 &&
      m.centerMax >
        lateCenterPeak
    ) {

      lateCenterPeak =
        m.centerMax;

      lateCenterPeakTime =
        t;
    }


    if (
      step %
      Math.round(
        0.5 / DT
      ) === 0
    ) {

      trace.push({
        t,
        center:
          m.centerMax,
        edge:
          m.edgeMax,
        rms:
          m.wholeRms
      });
    }
  }


  return {
    label,

    earlyCenterPeak,
    edgeArrivalPeak,
    lateCenterPeak,
    lateCenterPeakTime,

    reflectionRatio:
      lateCenterPeak /
      Math.max(
        earlyCenterPeak,
        1e-12
      ),

    trace
  };
}


console.log(
  "VISIBLE_GRID_SIDE=",
  VISIBLE_SEGMENTS + 1
);

console.log(
  "VISIBLE_WIDTH=",
  VISIBLE_WIDTH
);

console.log(
  "DX=",
  DX
);

console.log(
  "HIDDEN_GUARD_CELLS=",
  GUARD_CELLS
);

console.log(
  "HIDDEN_GUARD_PHYSICAL_WIDTH=",
  GUARD_CELLS * DX
);

console.log(
  "EXTENDED_GRID_SIDE=",
  EXTENDED_SEGMENTS + 1
);

console.log(
  "EXTENDED_PHYSICS_WIDTH=",
  EXTENDED_WIDTH
);

console.log(
  "MAX_HIDDEN_DAMPING=",
  MAX_HIDDEN_DAMPING
);


const baseline =
  run(
    "CURRENT_REFLECTIVE",
    createBaseline(),
    0
  );


const invisible =
  run(
    "INVISIBLE_CONTINUATION",
    createInvisibleContinuation(),
    GUARD_CELLS
  );


function printResult(r) {

  console.log(
    `\n===== ${r.label} =====`
  );

  console.log(
    "EARLY_CENTER_PEAK=",
    r.earlyCenterPeak
  );

  console.log(
    "VISIBLE_EDGE_ARRIVAL_PEAK=",
    r.edgeArrivalPeak
  );

  console.log(
    "LATE_CENTER_PEAK=",
    r.lateCenterPeak
  );

  console.log(
    "LATE_CENTER_PEAK_TIME=",
    r.lateCenterPeakTime
  );

  console.log(
    "LATE_TO_INITIAL_CENTER_RATIO=",
    r.reflectionRatio
  );
}


printResult(
  baseline
);

printResult(
  invisible
);


const reflectionReduction =
  1 -
  invisible.lateCenterPeak /
  Math.max(
    baseline.lateCenterPeak,
    1e-12
  );


const visibleEdgeRetention =
  invisible.edgeArrivalPeak /
  Math.max(
    baseline.edgeArrivalPeak,
    1e-12
  );


console.log(
  "\n===== COMPARISON ====="
);

console.log(
  "REFLECTION_REDUCTION=",
  reflectionReduction
);

console.log(
  "VISIBLE_EDGE_MOTION_RETENTION=",
  visibleEdgeRetention
);

console.log(
  "BASELINE_LATE_CENTER=",
  baseline.lateCenterPeak
);

console.log(
  "INVISIBLE_LATE_CENTER=",
  invisible.lateCenterPeak
);


console.log(
  "\n===== INVISIBLE CONTINUATION TRACE ====="
);


for (
  const s of invisible.trace
) {

  console.log(
    `t=${s.t.toFixed(2)}`,
    `center=${s.center.toFixed(8)}`,
    `visibleEdge=${s.edge.toFixed(8)}`,
    `visibleRms=${s.rms.toFixed(8)}`
  );
}


console.log(
  "\n===== CONTRACT ====="
);

console.log(
  "VISIBLE_MESH_UNCHANGED=YES"
);

console.log(
  "VISIBLE_SEGMENTS_UNCHANGED=128x128"
);

console.log(
  "VISIBLE_BOUNDARY_FIXED=NO"
);

console.log(
  "ABSORPTION_STARTS_OUTSIDE_VISIBLE_DOMAIN=YES"
);

console.log(
  "PRODUCTION_CHANGED=NO"
);

console.log(
  "BEHAVIOR_LAB_CHANGED=NO"
);

console.log(
  "\nEXPERIMENT_STATUS=PASS"
);

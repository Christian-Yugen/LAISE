import {
  RippleField
} from "../src/behavior-ripple-field-v13c.js";

import {
  OpenBoundaryRippleFieldV13C
} from "../src/behavior-open-boundary-field-v13c.js";


const WIDTH = 16;
const SEGMENTS = 128;

const DT = 1 / 120;
const DURATION = 10.5;


function metrics(
  heights
) {

  const side =
    SEGMENTS + 1;

  const center =
    SEGMENTS / 2;


  let centerMax = 0;
  let edgeMax = 0;


  for (
    let z = 0;
    z < side;
    z++
  ) {

    for (
      let x = 0;
      x < side;
      x++
    ) {

      const i =
        z * side + x;

      const value =
        Math.abs(
          heights[i]
        );


      const dx =
        x - center;

      const dz =
        z - center;


      if (
        Math.sqrt(
          dx * dx +
          dz * dz
        ) <=
        center * 0.15
      ) {

        centerMax =
          Math.max(
            centerMax,
            value
          );
      }


      const edgeDistance =
        Math.min(
          x,
          z,
          SEGMENTS - x,
          SEGMENTS - z
        );


      if (
        edgeDistance <=
        center * 0.10
      ) {

        edgeMax =
          Math.max(
            edgeMax,
            value
          );
      }
    }
  }


  return {
    centerMax,
    edgeMax
  };
}


function run(
  field
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

      field.advance(
        DT
      );
    }


    const m =
      metrics(
        field.heights
      );


    if (
      t <= 1.25
    ) {

      earlyCenterPeak =
        Math.max(
          earlyCenterPeak,
          m.centerMax
        );
    }


    if (
      t >= 2 &&
      t <= 4
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
  }


  return {
    earlyCenterPeak,
    edgeArrivalPeak,
    lateCenterPeak,
    lateCenterPeakTime
  };
}


const legacy =
  new RippleField(
    WIDTH,
    WIDTH,
    SEGMENTS,
    SEGMENTS
  );


const open =
  new OpenBoundaryRippleFieldV13C(
    WIDTH,
    WIDTH,
    SEGMENTS,
    SEGMENTS
  );


const a =
  run(
    legacy
  );

const b =
  run(
    open
  );


console.log(
  "===== R5 IMPLEMENTATION AUDIT ====="
);

console.log(
  "VISIBLE_HEIGHT_COUNT=",
  open.heights.length
);

console.log(
  "EXPECTED_VISIBLE_HEIGHT_COUNT=",
  129 * 129
);

console.log(
  "BOUNDARY_DEBUG=",
  JSON.stringify(
    open.debugBoundary
  )
);


console.log(
  "\n===== LEGACY V1.2 ====="
);

console.log(
  "EARLY_CENTER_PEAK=",
  a.earlyCenterPeak
);

console.log(
  "EDGE_ARRIVAL_PEAK=",
  a.edgeArrivalPeak
);

console.log(
  "LATE_CENTER_PEAK=",
  a.lateCenterPeak
);

console.log(
  "LATE_CENTER_PEAK_TIME=",
  a.lateCenterPeakTime
);


console.log(
  "\n===== OPEN V1.3C ====="
);

console.log(
  "EARLY_CENTER_PEAK=",
  b.earlyCenterPeak
);

console.log(
  "EDGE_ARRIVAL_PEAK=",
  b.edgeArrivalPeak
);

console.log(
  "LATE_CENTER_PEAK=",
  b.lateCenterPeak
);

console.log(
  "LATE_CENTER_PEAK_TIME=",
  b.lateCenterPeakTime
);


const earlyRetention =
  b.earlyCenterPeak /
  a.earlyCenterPeak;


const edgeRetention =
  b.edgeArrivalPeak /
  a.edgeArrivalPeak;


const reflectionReduction =
  1 -
  b.lateCenterPeak /
  a.lateCenterPeak;


console.log(
  "\n===== COMPARISON ====="
);

console.log(
  "INITIAL_WAVE_RETENTION=",
  earlyRetention
);

console.log(
  "VISIBLE_EDGE_MOTION_RETENTION=",
  edgeRetention
);

console.log(
  "REFLECTION_REDUCTION=",
  reflectionReduction
);


const gates = {

  visibleHeightContract:
    open.heights.length ===
    129 * 129,

  initialWavePreserved:
    earlyRetention >= 0.995 &&
    earlyRetention <= 1.005,

  visibleEdgeMoves:
    b.edgeArrivalPeak > 0,

  reflectionReduced:
    reflectionReduction >= 0.90,

  coordinateScale:
    Math.abs(
      open.debugBoundary.coordinateScaleX -
      16 / 22
    ) < 1e-12
};


for (
  const [
    name,
    pass
  ]
  of Object.entries(
    gates
  )
) {

  console.log(
    `${name.toUpperCase()}=${pass ? "PASS" : "FAIL"}`
  );
}


const allPass =
  Object.values(
    gates
  ).every(Boolean);


console.log(
  `R5_PHYSICS_CONTRACT=${allPass ? "PASS" : "FAIL"}`
);

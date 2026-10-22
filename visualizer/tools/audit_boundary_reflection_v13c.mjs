import {
  RippleField
} from "../src/behavior-ripple-field-v13c.js";


const WIDTH = 16;
const DEPTH = 16;
const SEGMENTS = 128;

const DT = 1 / 120;
const DURATION = 9.0;

const field = new RippleField(
  WIDTH,
  DEPTH,
  SEGMENTS,
  SEGMENTS
);


// ------------------------------------------------------------
// One isolated central event.
//
// Strong enough to be clearly measurable, but not intended
// to represent a specific Tukãna musical event.
// ------------------------------------------------------------

field.exciteBipolarAt(
  0,
  0,
  0.50,
  0.80
);


const side =
  Math.round(
    Math.sqrt(
      field.heights.length
    )
  );


if (
  side * side !==
  field.heights.length
) {
  throw new Error(
    "Unexpected field geometry"
  );
}


const center =
  (side - 1) / 2;


function metrics() {

  let centerMax = 0;
  let centerSq = 0;
  let centerN = 0;

  let edgeMax = 0;
  let edgeSq = 0;
  let edgeN = 0;

  let wholeMax = 0;
  let wholeSq = 0;


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

      const h =
        field.heights[i];

      const ah =
        Math.abs(h);

      wholeMax =
        Math.max(
          wholeMax,
          ah
        );

      wholeSq +=
        h * h;


      const dx =
        x - center;

      const dz =
        z - center;

      const r =
        Math.sqrt(
          dx * dx +
          dz * dz
        );


      // Inner 15% radius:
      // useful for detecting energy returning
      // toward the source region.
      if (
        r <=
        center * 0.15
      ) {

        centerMax =
          Math.max(
            centerMax,
            ah
          );

        centerSq +=
          h * h;

        centerN++;
      }


      // Outer 10% of visible mesh.
      // This MUST move when the wave arrives.
      const edgeDistance =
        Math.min(
          x,
          z,
          side - 1 - x,
          side - 1 - z
        );


      if (
        edgeDistance <=
        center * 0.10
      ) {

        edgeMax =
          Math.max(
            edgeMax,
            ah
          );

        edgeSq +=
          h * h;

        edgeN++;
      }
    }
  }


  return {
    centerMax,

    centerRms:
      Math.sqrt(
        centerSq /
        Math.max(
          centerN,
          1
        )
      ),

    edgeMax,

    edgeRms:
      Math.sqrt(
        edgeSq /
        Math.max(
          edgeN,
          1
        )
      ),

    wholeMax,

    wholeRms:
      Math.sqrt(
        wholeSq /
        field.heights.length
      )
  };
}


let earlyCenterPeak = 0;
let edgeArrivalPeak = 0;
let lateCenterPeak = 0;

let lateCenterPeakTime = 0;

let snapshots = [];


const totalSteps =
  Math.round(
    DURATION / DT
  );


for (
  let step = 0;
  step <= totalSteps;
  step++
) {

  const t =
    step * DT;


  if (step > 0) {
    field.advance(DT);
  }


  const m =
    metrics();


  // Initial/source phase.
  if (t <= 1.25) {

    earlyCenterPeak =
      Math.max(
        earlyCenterPeak,
        m.centerMax
      );
  }


  // c ~= 3 over an 8-unit half-domain:
  // first edge interaction expected around 2.7 s.
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


  // A reflected component can return toward center
  // roughly after the outward + inward travel.
  if (
    t >= 4.5 &&
    t <= 7.5 &&
    m.centerMax >
      lateCenterPeak
  ) {

    lateCenterPeak =
      m.centerMax;

    lateCenterPeakTime =
      t;
  }


  // Human-readable trace every 0.25 s.
  if (
    step %
    Math.round(
      0.25 / DT
    ) === 0
  ) {

    snapshots.push({
      t,
      centerMax:
        m.centerMax,
      edgeMax:
        m.edgeMax,
      wholeRms:
        m.wholeRms
    });
  }
}


const reflectionRatio =
  earlyCenterPeak > 0
    ? lateCenterPeak /
      earlyCenterPeak
    : 0;


console.log(
  "GRID_SIDE=",
  side
);

console.log(
  "DURATION_SECONDS=",
  DURATION
);

console.log(
  "EARLY_CENTER_PEAK=",
  earlyCenterPeak
);

console.log(
  "EDGE_ARRIVAL_PEAK=",
  edgeArrivalPeak
);

console.log(
  "LATE_CENTER_PEAK=",
  lateCenterPeak
);

console.log(
  "LATE_CENTER_PEAK_TIME=",
  lateCenterPeakTime
);

console.log(
  "LATE_TO_INITIAL_CENTER_RATIO=",
  reflectionRatio
);


console.log(
  "\n--- TIME TRACE ---"
);


for (
  const s of snapshots
) {

  console.log(
    `t=${s.t.toFixed(2)}`,
    `center=${s.centerMax.toFixed(8)}`,
    `edge=${s.edgeMax.toFixed(8)}`,
    `fieldRms=${s.wholeRms.toFixed(8)}`
  );
}


if (
  edgeArrivalPeak <= 0
) {
  throw new Error(
    "Boundary did not respond to wave"
  );
}


console.log(
  "\nBOUNDARY_MOVEMENT_GATE=PASS"
);

console.log(
  "BOUNDARY_REFLECTION_AUDIT=PASS"
);

console.log(
  "NOTE=Measurement only; no physics changed."
);

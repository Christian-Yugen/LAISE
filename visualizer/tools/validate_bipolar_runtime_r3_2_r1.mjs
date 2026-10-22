import {
  RippleField
} from "../src/behavior-ripple-field-v13c.js";


const field =
  new RippleField(
    16,
    16,
    128,
    128
  );


field.exciteBipolarAt(
  0,
  0,
  0.5,
  0.8
);


const velocityMin =
  Math.min(
    ...field.velocities
  );

const velocityMax =
  Math.max(
    ...field.velocities
  );


field.advance(
  1 / 120
);


const heightMin =
  Math.min(
    ...field.heights
  );

const heightMax =
  Math.max(
    ...field.heights
  );


console.log(
  "VELOCITY_MIN=",
  velocityMin
);

console.log(
  "VELOCITY_MAX=",
  velocityMax
);

console.log(
  "HEIGHT_MIN=",
  heightMin
);

console.log(
  "HEIGHT_MAX=",
  heightMax
);


if (
  !(velocityMin < 0) ||
  !(velocityMax > 0) ||
  !(heightMin < 0) ||
  !(heightMax > 0)
) {

  throw new Error(
    "Signed field gate failed"
  );
}


console.log(
  "SIGNED_RUNTIME_GATE=PASS"
);

const PHYSICS_DT = 1 / 120;
const IMPULSE_GAIN = 20;

const clamp = (value, low, high) =>
  Math.max(low, Math.min(high, value));


export class BehaviorTimelineV13C {

  constructor(data) {

    if (
      !data ||
      data.schema !==
        "laise-v1.3c-visible-behavior-runtime-v1" ||
      !Array.isArray(data.behaviors)
    ) {
      throw new Error(
        "Invalid V1.3C behavior runtime"
      );
    }


    this.data = data;

    this.kImpulse =
      data.calibration.kImpulse;

    this.kContinuous =
      data.calibration.kContinuous;

    this.p10 =
      data.calibration.continuousDriveP10;

    this.p99 =
      data.calibration.continuousDriveP99;


    this.tie =
      data.calibration.arbitration.tie;

    this.hysteresis =
      data.calibration.arbitration.hysteresis;

    this.hold =
      data.calibration.arbitration.holdSeconds;

    this.strongChange =
      data.calibration.arbitration.strongChangeRatio;


    this.continuous =
      data.behaviors
        .filter(
          behavior =>
            behavior.continuous.length > 0
        )
        .map(
          behavior => ({
            ...behavior,
            sampleIndex: 0
          })
        );


    this.attacks =
      data.behaviors
        .flatMap(
          behavior => {

            const discrete =
              behavior.attacks.map(
                attack => ({
                  ...attack,

                  physicalDrive:
                    attack.drive,

                  candidateDrive:
                    attack.drive,

                  reinforcement:
                    false,

                  behaviorId:
                    behavior.behaviorId,

                  source:
                    behavior.source,

                  primitive:
                    behavior.primitive,

                  baseWidth:
                    behavior.baseWidth
                })
              );


            const reinforcement =
              (
                behavior.reinforcementAttacks ??
                []
              )
                .filter(
                  attack =>
                    (
                    attack.physicalAttackDrive ??
                    attack.residualDrive
                  ) > 0
                )
                .map(
                  attack => ({
                    ...attack,

                    drive:
                      (
                        attack.physicalAttackDrive ??
                        attack.residualDrive
                      ),

                    physicalDrive:
                      (
                        attack.physicalAttackDrive ??
                        attack.residualDrive
                      ),

                    /*
                      Anchor arbitration sees the
                      actual musical attack strength.

                      Physics receives only the
                      transient excess above the
                      continuous baseline.
                    */
                    candidateDrive:
                      attack.sourceDrive,

                    reinforcement:
                      true,

                    behaviorId:
                      behavior.behaviorId,

                    source:
                      behavior.source,

                    primitive:
                      behavior.primitive,

                    baseWidth:
                      behavior.baseWidth
                  })
                );


            return [
              ...discrete,
              ...reinforcement
            ];
          }
        )
        .sort(
          (a, b) =>
            a.time - b.time ||
            a.source.localeCompare(
              b.source
            ) ||
            Number(a.reinforcement) -
            Number(b.reinforcement)
        );


    this.recentAttacks =
      new Map();


    this.debug = {
      anchorSource: "—",
      anchorDrive: 0,
      anchorX: 0,
      anchorZ: 0,
      footprintScale: 1,
      activeContinuous: 0
    };


    this.seek(0);
  }


  lowerBoundAttack(time) {

    let low = 0;
    let high = this.attacks.length;

    while (low < high) {

      const middle =
        (low + high) >>> 1;

      if (
        this.attacks[middle].time <
        time
      ) {
        low = middle + 1;
      } else {
        high = middle;
      }
    }

    return low;
  }


  seek(time) {

    this.lastTime = time;
    this.simulationTime = time;

    this.attackIndex =
      this.lowerBoundAttack(time);

    this.recentAttacks.clear();

    this.anchorSource = null;
    this.anchorX = 0;
    this.anchorZ = 0;
    this.anchorScore = 0;
    this.anchorSince = time;
    this.anchorLastSeen = time;


    for (
      const behavior
      of this.continuous
    ) {

      let low = 0;
      let high =
        behavior.continuous.length;

      while (low < high) {

        const middle =
          (low + high) >>> 1;

        if (
          behavior.continuous[middle][0]
          <= time
        ) {
          low = middle + 1;
        } else {
          high = middle;
        }
      }

      behavior.sampleIndex =
        Math.max(
          0,
          low - 1
        );
    }
  }


  sampleAt(
    behavior,
    time
  ) {

    const samples =
      behavior.continuous;

    if (
      time < behavior.startTime ||
      time >= behavior.endTime ||
      samples.length === 0
    ) {
      return null;
    }


    while (
      behavior.sampleIndex + 1 <
        samples.length &&
      samples[
        behavior.sampleIndex + 1
      ][0] <= time + 1e-12
    ) {
      behavior.sampleIndex++;
    }


    const row =
      samples[
        behavior.sampleIndex
      ];


    return {
      source:
        behavior.source,

      drive:
        row[1],

      x:
        row[2],

      z:
        row[3],

      baseWidth:
        behavior.baseWidth,

      primitive:
        behavior.primitive
    };
  }


  footprintScale(
    drive
  ) {

    /*
      Absolute-preserving provisional visual mapping.

      P10 -> 0.55x base footprint
      P99 -> 1.45x base footprint

      The musical amplitude itself is NOT normalized.
      This only controls the initial spatial footprint.
    */

    const safe =
      Math.max(
        drive,
        this.p10
      );

    const denominator =
      Math.log(this.p99) -
      Math.log(this.p10);

    const u =
      denominator > 0
        ? clamp(
            (
              Math.log(safe) -
              Math.log(this.p10)
            ) / denominator,
            0,
            1
          )
        : 0;


    return (
      0.55 +
      0.90 * u
    );
  }


  addCandidate(
    candidates,
    candidate
  ) {

    const previous =
      candidates.get(
        candidate.source
      );

    if (
      !previous ||
      candidate.drive >
        previous.drive
    ) {
      candidates.set(
        candidate.source,
        candidate
      );
    }
  }


  chooseAnchor(
    candidates,
    time
  ) {

    if (
      candidates.size === 0
    ) {
      return;
    }


    const ranked =
      [...candidates.values()]
        .sort(
          (a, b) =>
            b.drive - a.drive ||
            a.source.localeCompare(
              b.source
            )
        );


    const best =
      ranked[0];


    if (!this.anchorSource) {

      this.anchorSource =
        best.source;

      this.anchorX =
        best.x;

      this.anchorZ =
        best.z;

      this.anchorScore =
        best.drive;

      this.anchorSince =
        time;

      this.anchorLastSeen =
        time;

      return;
    }


    const current =
      candidates.get(
        this.anchorSource
      );


    if (current) {

      this.anchorX =
        current.x;

      this.anchorZ =
        current.z;

      this.anchorScore =
        current.drive;

      this.anchorLastSeen =
        time;


      if (
        best.source ===
        this.anchorSource
      ) {
        return;
      }


      const tieLimit =
        current.drive *
        (1 + this.tie);


      if (
        best.drive <=
        tieLimit
      ) {
        return;
      }


      const immediate =
        best.drive >=
        current.drive *
        this.strongChange;


      const hysteresisPassed =
        (
          time -
          this.anchorSince
        ) >= this.hold &&
        best.drive >
          current.drive *
          (1 + this.hysteresis);


      if (
        !immediate &&
        !hysteresisPassed
      ) {
        return;
      }

    } else {

      /*
        Keep the previous compositional anchor
        briefly after its causal evidence ends.
        This prevents visual anchor chatter.
      */

      if (
        time -
        this.anchorLastSeen <
        this.hold
      ) {
        return;
      }
    }


    this.anchorSource =
      best.source;

    this.anchorX =
      best.x;

    this.anchorZ =
      best.z;

    this.anchorScore =
      best.drive;

    this.anchorSince =
      time;

    this.anchorLastSeen =
      time;
  }


  stepFixed(
    nextTime,
    field
  ) {

    const candidates =
      new Map();

    const continuousStates =
      [];


    /*
      Expire old attack evidence.
    */

    for (
      const [
        source,
        recent
      ]
      of this.recentAttacks
    ) {

      if (
        recent.until <
        nextTime
      ) {

        this.recentAttacks.delete(
          source
        );

      } else {

        this.addCandidate(
          candidates,
          recent
        );
      }
    }


    /*
      Continuous musical evidence.
    */

    for (
      const behavior
      of this.continuous
    ) {

      const state =
        this.sampleAt(
          behavior,
          nextTime
        );

      if (!state) {
        continue;
      }


      continuousStates.push(
        state
      );

      this.addCandidate(
        candidates,
        state
      );
    }


    /*
      Discrete attacks that occur during
      this 120 Hz physics interval.
    */

    const stepAttacks = [];


    while (
      this.attackIndex <
        this.attacks.length &&
      this.attacks[
        this.attackIndex
      ].time <= nextTime + 1e-12
    ) {

      const attack =
        this.attacks[
          this.attackIndex++
        ];


      if (
        attack.time >
        this.simulationTime - 1e-12
      ) {

        stepAttacks.push(
          attack
        );


        const recent = {
          source:
            attack.source,

          drive:
            attack.candidateDrive,

          x:
            attack.x,

          z:
            attack.z,

          baseWidth:
            attack.baseWidth,

          primitive:
            attack.primitive,

          until:
            attack.time +
            this.hold
        };


        const old =
          this.recentAttacks.get(
            attack.source
          );


        if (
          !old ||
          recent.drive >=
            old.drive
        ) {

          this.recentAttacks.set(
            attack.source,
            recent
          );
        }


        this.addCandidate(
          candidates,
          recent
        );
      }
    }


    /*
      V1.3B arbitration constants now organize
      the visual reference frame.

      No roleCode gain is applied.
    */

    this.chooseAnchor(
      candidates,
      nextTime
    );


    const anchorX =
      this.anchorX;

    const anchorZ =
      this.anchorZ;


    /*
      Sustains and rolls:
      continuous physical force.

      dv =
        Kcontinuous
        * physicalDrive(t)
        * dt

      RippleField impulseGain is 20, therefore
      equivalent strength is dv / 20.
    */

    for (
      const state
      of continuousStates
    ) {

      const scale =
        this.footprintScale(
          state.drive
        );

      const width =
        state.baseWidth *
        scale;


      const equivalentStrength =
        (
          this.kContinuous *
          state.drive *
          PHYSICS_DT
        ) / IMPULSE_GAIN;


      field.exciteBipolarAt(
        state.x - anchorX,
        state.z - anchorZ,
        equivalentStrength,
        width
      );
    }


    /*
      Impulses and pulse sequences:
      discrete physical impulse.

      dv =
        Kimpulse
        * physicalDrive_attack
    */

    for (
      const attack
      of stepAttacks
    ) {

      const scale =
        this.footprintScale(
          attack.physicalDrive
        );

      const width =
        attack.baseWidth *
        scale;


      const equivalentStrength =
        (
          this.kImpulse *
          attack.physicalDrive
        ) / IMPULSE_GAIN;


      field.exciteBipolarAt(
        attack.x - anchorX,
        attack.z - anchorZ,
        equivalentStrength,
        width
      );
    }


    field.advance(
      PHYSICS_DT
    );


    const anchorCandidate =
      this.anchorSource
        ? candidates.get(
            this.anchorSource
          )
        : null;


    const debugDrive =
      anchorCandidate?.drive ??
      this.anchorScore ??
      0;


    this.debug = {
      anchorSource:
        this.anchorSource ?? "—",

      anchorDrive:
        debugDrive,

      anchorX:
        anchorX,

      anchorZ:
        anchorZ,

      footprintScale:
        debugDrive > 0
          ? this.footprintScale(
              debugDrive
            )
          : 1,

      activeContinuous:
        continuousStates.length
    };


    this.simulationTime =
      nextTime;
  }


  step(
    targetTime,
    playing,
    field
  ) {

    if (
      !Number.isFinite(
        targetTime
      )
    ) {
      return false;
    }


    if (!playing) {
      return false;
    }


    if (
      targetTime <
      this.lastTime
    ) {
      this.seek(
        targetTime
      );
      return false;
    }


    /*
      Musical clock remains sovereign.

      The field advances in exact 120 Hz
      physics increments until it catches
      the media clock.
    */

    while (
      this.simulationTime +
      PHYSICS_DT <=
      targetTime + 1e-10
    ) {

      this.stepFixed(
        this.simulationTime +
        PHYSICS_DT,
        field
      );
    }


    this.lastTime =
      targetTime;

    return true;
  }
}

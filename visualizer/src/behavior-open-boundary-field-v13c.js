import {
  RippleField,
  RIPPLE_SETTINGS
} from "./behavior-ripple-field-v13c.js";


const clamp =
  (value, low, high) =>
    Math.max(
      low,
      Math.min(
        high,
        value
      )
    );


function smoothstep01(value) {

  const x =
    clamp(
      value,
      0,
      1
    );

  return (
    x *
    x *
    (3 - 2 * x)
  );
}


/*
  V1.3C R5 — Invisible continuation / open-boundary lab.

  The visible 16 x 16 terrain remains unchanged.

  Internally the physical field extends beyond the camera.
  The visible boundary is NOT a wall and receives no special
  absorption.

  Waves cross the visible edge into an invisible continuation,
  where progressive damping absorbs them before they can return
  from the numerical boundary.

  Important contracts:

  - visible geometry remains 128 x 128 segments;
  - visible heights remain 129 x 129;
  - dx/dz remain identical to the legacy field;
  - T007 normalized coordinates retain the visible 16 x 16 scale;
  - propagation speed remains unchanged;
  - bipolar excitation remains unchanged;
  - no visual headroom mapping is performed here.
*/

export class OpenBoundaryRippleFieldV13C {

  constructor(
    visibleWidth,
    visibleDepth,
    segmentsX,
    segmentsZ,
    {
      guardCells = 24,
      maxHiddenDamping = 6
    } = {}
  ) {

    this.visibleWidth =
      visibleWidth;

    this.visibleDepth =
      visibleDepth;

    this.visibleColumns =
      segmentsX + 1;

    this.visibleRows =
      segmentsZ + 1;

    this.guardCells =
      guardCells;

    this.maxHiddenDamping =
      maxHiddenDamping;


    const dx =
      visibleWidth /
      segmentsX;

    const dz =
      visibleDepth /
      segmentsZ;


    this.dx = dx;
    this.dz = dz;


    this.extendedSegmentsX =
      segmentsX +
      2 * guardCells;

    this.extendedSegmentsZ =
      segmentsZ +
      2 * guardCells;


    this.extendedWidth =
      visibleWidth +
      2 * guardCells * dx;

    this.extendedDepth =
      visibleDepth +
      2 * guardCells * dz;


    this.coordinateScaleX =
      visibleWidth /
      this.extendedWidth;

    this.coordinateScaleZ =
      visibleDepth /
      this.extendedDepth;


    this._field =
      new RippleField(
        this.extendedWidth,
        this.extendedDepth,
        this.extendedSegmentsX,
        this.extendedSegmentsZ
      );


    /*
      Public heights are ONLY the visible central window.

      Renderer therefore continues seeing exactly:
      129 x 129 = 16641 samples.
    */

    this.heights =
      new Float32Array(
        this.visibleColumns *
        this.visibleRows
      );


    this._configureHiddenAbsorption();
    this._copyVisibleWindow();
  }


  _configureHiddenAbsorption() {

    const field =
      this._field;

    const centerCol =
      (field.columns - 1) /
      2;

    const centerRow =
      (field.rows - 1) /
      2;


    const visibleHalfX =
      (this.visibleColumns - 1) /
      2;

    const visibleHalfZ =
      (this.visibleRows - 1) /
      2;


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


        /*
          hiddenDepth == 0 throughout the entire visible
          terrain, INCLUDING its outermost visible vertices.
        */

        const outsideX =
          Math.max(
            0,
            Math.abs(
              col - centerCol
            ) - visibleHalfX
          );


        const outsideZ =
          Math.max(
            0,
            Math.abs(
              row - centerRow
            ) - visibleHalfZ
          );


        const normalizedHiddenDepth =
          Math.max(
            outsideX /
              this.guardCells,

            outsideZ /
              this.guardCells
          );


        const sponge =
          smoothstep01(
            normalizedHiddenDepth
          );


        const localDamping =
          RIPPLE_SETTINGS.damping +
          this.maxHiddenDamping *
          sponge;


        field.attenuation[i] =
          Math.exp(
            -localDamping *
            field.step
          );
      }
    }
  }


  _mapVisibleCoordinate(
    value,
    scale
  ) {

    /*
      Preserve legacy visible-domain semantics:

      first clamp T007/anchor result to [-1,+1],
      THEN map the visible 16-unit domain into the
      central portion of the 22-unit physical domain.

      +1 therefore remains physical +8, not +11.
    */

    return (
      clamp(
        value,
        -1,
        1
      ) *
      scale
    );
  }


  _copyVisibleWindow() {

    const source =
      this._field.heights;

    const sourceColumns =
      this._field.columns;


    const guard =
      this.guardCells;


    for (
      let visibleRow = 0;
      visibleRow < this.visibleRows;
      visibleRow++
    ) {

      const sourceStart =
        (
          visibleRow +
          guard
        ) *
        sourceColumns +
        guard;


      const targetStart =
        visibleRow *
        this.visibleColumns;


      this.heights.set(
        source.subarray(
          sourceStart,
          sourceStart +
          this.visibleColumns
        ),
        targetStart
      );
    }
  }


  exciteAt(
    normalizedX,
    normalizedZ,
    strength,
    width = 0.7
  ) {

    this._field.exciteAt(
      this._mapVisibleCoordinate(
        normalizedX,
        this.coordinateScaleX
      ),

      this._mapVisibleCoordinate(
        normalizedZ,
        this.coordinateScaleZ
      ),

      strength,
      width
    );
  }


  exciteBipolarAt(
    normalizedX,
    normalizedZ,
    strength,
    width = 0.7
  ) {

    this._field.exciteBipolarAt(
      this._mapVisibleCoordinate(
        normalizedX,
        this.coordinateScaleX
      ),

      this._mapVisibleCoordinate(
        normalizedZ,
        this.coordinateScaleZ
      ),

      strength,
      width
    );
  }


  advance(
    delta
  ) {

    this._field.advance(
      delta
    );

    this._copyVisibleWindow();
  }


  reset() {

    this._field.reset();

    this.heights.fill(
      0
    );
  }


  get impulseCount() {

    return (
      this._field.impulseCount
    );
  }


  get time() {

    return (
      this._field.time
    );
  }


  get debugBoundary() {

    return {
      visibleWidth:
        this.visibleWidth,

      extendedWidth:
        this.extendedWidth,

      visibleGrid:
        `${this.visibleColumns}x${this.visibleRows}`,

      extendedGrid:
        `${this._field.columns}x${this._field.rows}`,

      guardCells:
        this.guardCells,

      coordinateScaleX:
        this.coordinateScaleX,

      coordinateScaleZ:
        this.coordinateScaleZ,

      maxHiddenDamping:
        this.maxHiddenDamping
    };
  }
}

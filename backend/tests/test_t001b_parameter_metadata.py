from pathlib import Path
from pedalboard import load_plugin

PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3"
    r"\Contents\x86_64-win\dearVR PRO 2.vst3"
)

print("=" * 80)
print("LAISE — T001-B")
print("dearVR PRO 2 Parameter Metadata")
print("=" * 80)

plugin = load_plugin(str(PLUGIN_PATH))

important_parameters = [
    "coordinate_system",
    "azimuth",
    "elevation",
    "distance",
    "x",
    "y",
    "z",
    "direct_gain",
    "azimuth_scale",
    "distance_scale",
    "occlusion",
    "virtual_acoustics",
    "room_size",
    "stereo_width",
    "master_gain_db",
    "clarity",
]

for name in important_parameters:

    parameter = plugin.parameters[name]

    print("\n" + "-" * 80)
    print(f"PARAMETER: {name}")
    print("-" * 80)

    print(f"raw_value:       {parameter.raw_value}")

    attributes = [
        "min_value",
        "max_value",
        "default_value",
        "is_discrete",
        "is_boolean",
        "is_integer",
        "valid_values",
        "value",
    ]

    for attribute in attributes:

        try:
            value = getattr(parameter, attribute)
            print(f"{attribute:16}: {value}")

        except Exception as exc:
            print(
                f"{attribute:16}: "
                f"<not available: {type(exc).__name__}>"
            )

print("\n" + "=" * 80)
print("T001-B COMPLETE")
print("=" * 80)

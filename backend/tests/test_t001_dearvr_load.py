import sys
import platform
import traceback
from pathlib import Path

import pedalboard
from pedalboard import load_plugin


PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3\Contents\x86_64-win\dearVR PRO 2.vst3"
)


print("=" * 70)
print("LAISE — T001")
print("dearVR PRO 2 / Pedalboard Integration Test")
print("=" * 70)

print(f"\nPython:       {sys.version}")
print(f"Platform:     {platform.platform()}")
print(f"Pedalboard:   {pedalboard.__version__}")
print(f"Plugin path:  {PLUGIN_PATH}")
print(f"Path exists:  {PLUGIN_PATH.exists()}")

if not PLUGIN_PATH.exists():
    print("\nRESULT: FAIL")
    print("Reason: dearVR PRO 2 VST3 was not found.")
    raise SystemExit(1)

print("\nAttempting to load dearVR PRO 2...")

try:
    plugin = load_plugin(str(PLUGIN_PATH))

    print("\nPLUGIN LOADED SUCCESSFULLY")
    print("-" * 70)

    print(f"Name:          {plugin.name}")
    print(f"Manufacturer:  {plugin.manufacturer_name}")
    print(f"Identifier:    {plugin.identifier}")
    print(f"Is effect:     {plugin.is_effect}")
    print(f"Latency:       {plugin.reported_latency_samples} samples")

    parameters = plugin.parameters

    print(f"\nParameter count: {len(parameters)}")
    print("\nPARAMETERS")
    print("-" * 70)

    for index, (name, parameter) in enumerate(parameters.items(), start=1):
        print(
            f"{index:03d} | "
            f"{name} | "
            f"value={parameter.raw_value}"
        )

    print("\n" + "=" * 70)
    print("T001-A RESULT: PASS")
    print("=" * 70)

except Exception as exc:
    print("\n" + "=" * 70)
    print("T001-A RESULT: FAIL")
    print("=" * 70)

    print(f"\nException type: {type(exc).__name__}")
    print(f"Message: {exc}")

    print("\nTRACEBACK")
    print("-" * 70)
    traceback.print_exc()

    raise SystemExit(1)
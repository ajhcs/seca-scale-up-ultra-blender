# Portable synthetic workflow study

`study.py` is a small independent, deterministic fiction for testing presentation and event handling. It implements synthetic gross input, tare, hold/release, kilogram/pound display, numeric `SYNTH-` fixtures, and a local mock transfer with retry and lost-acknowledgement scenarios. It has no networking, hardware, calibration, height sensor or patient-data connection. Timing, state transitions and calculations are study decisions and are not a claim about seca behavior or the Blender script's complete behavior.

The output is a Python dictionary for a future adapter; this package does not wire it to USD, a display, audio or an interactive runtime. Run `python3 scripts/run_synthetic_study.py` from the package root for the included scenarios. `reset_live()` preserves pending transfer state and outbox/receiver records within that instance; nothing is persisted automatically outside the process.

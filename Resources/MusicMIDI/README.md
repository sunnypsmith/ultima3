> Historical conversion assets: the current application uses the C64 SID
> soundtrack in `Resources/MusicSID`. This directory and the conversion tools
> remain for reference and are not copied into the app or used as a fallback.

# MIDI Playback Assets

The MIDI files are generated from the original `Resources/Music/Song_*.mov`
tracks with `python3 scripts/convert-quicktime-music.py`.

Playback uses an AVAudioEngine, an AVAudioSequencer, and Apple's multi-timbral
General MIDI synth with a bundled SoundFont. Original MIDI channels, program
changes, controllers, and channel-10 percussion remain intact. Independent
music volume is applied at the mixer, including a true zero-volume setting;
the music bus reserves 6 dB of headroom. Song changes and stops do not sleep
on the game thread.

A locally supplied FluidR3 GM bank takes priority when present;
the distributable fallback is GeneralUser GS. The goal is a consistent musical
arrangement, not QuickTime or vintage-chip emulation.

## Instrument fidelity

The default GM bank is not an exact recreation of LairWare's QuickTime
instruments or the C64 SID. Identical MIDI programs can sound quite different
with a different bank. For comparison, macOS's own installed Apple DLS bank can
be selected with U3_MIDI_SOUNDBANK; Apple samples are not copied into this project.
It is a candidate for comparison with LairWare, not a verified exact match to
every historical QuickTime release.

The original Song_A requests a GS variation, "Choir Aahs 2" (0x1035), whose
ordinary GM fallback is Choir Aahs (0x35). Generate comparison MIDI preserving
the requested bank variations without changing the default assets:

```sh
python3 scripts/convert-quicktime-music.py --preserve-gs --output Build/MIDI-Apple
```

The audio diagnostic accepts U3_AUDIO_MIDI_DIRECTORY to audition that directory.
The default conversion stays compatible with GM-only banks. A C64 soundtrack
requires the original SID program and SID emulation to reproduce its synthesis.

Upstream: https://github.com/urish/cinto/blob/master/media/FluidR3%20GM.sf2
Original SoundFont: FluidR3 GM by Frank Wen, released under the MIT license.
SoundFont SHA-256:
`eebdac4b1f95625bf2902b77838769111cb478fb9d2c66aa8e9a8ae80fe7d0c0`

The FluidR3 attribution and license are included as `FluidR3-GM-LICENSE.txt`.
The retained GeneralUser GS comparison bank is covered by
`GeneralUser-GS-LICENSE.txt`.

Conversion restores General MIDI program assignments, routes percussion to
channel 10, reads source media timescale, and handles extended notes and
variable-length events. Supported main-sequence volume, pan, reverb, and chorus
controls are translated. QuickTime-specific instrument variants use their GM
fallback by default; --preserve-gs retains supported GS bank selections.
Tune-difference editing sequences, used-note metadata, and header
MIDI-channel metadata are not played as additional notes. This is a reader for
the bundled tracks, not a general-purpose QuickTime music converter. Original
movies remain the source of truth.

Validation:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_music_conversion.py
```

The app's `U3_AUDIO_SELF_TEST=1` diagnostic renders MIDI offline without
opening an audio output device. It checks all ten songs, multi-instrument
track counts, non-silent finite output, independent volume and mute, and
stopping. Set `U3_AUDIO_RENDER_DIRECTORY=/absolute/path` to also save WAV
previews. The effects checks decode all 36 PCM assets without playing them.

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` for
music conversion, effects-asset completeness and fidelity, and silent playback
behavior checks. On macOS the behavior checks exercise the current effects
implementation with a substitute player and synthetic PCM fixtures; they
also check music servicing during native input waits.

## Sound effects

The PCM files retain their original sample rates and decoded waveforms.
Several original recordings already contain clipping; playback cannot recover
those lost details. The effects player measures each asset once and only
attenuates: integrated RMS is limited to -16 dBFS and sample peaks to -3 dBFS.
Quiet footsteps are never amplified. Cached player pools, repeated-trigger
coalescing, and bounded overlapping voices reduce loading work and sound pileups.
The original MP3 level-up effect is also supplied as PCM.

For A/B listening tests, set `U3_MIDI_SOUNDBANK` to an external `.sf2` file.
The MIDI files retain
the instrument programs extracted from the original QuickTime tracks.

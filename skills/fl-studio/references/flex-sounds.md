# FLEX sound guide

FL's API can't load plugins, so every melodic sound comes from FLEX instances
already in the project. The Default template has one ("FLEX Bass", channel 4);
`fl_clone_channel` makes more, `fl_route_channel` gives each its own mixer insert,
`fl_flex_select_pack` + `fl_flex_load_preset` pick the sound.

`fl_flex_list_packs` returns the installed packs; `fl_flex_select_pack` returns that
pack's presets. The lists below are from a stock FL Studio 2025 install with the free FLEX packs (2026-10).

## Packs by role

| Role | Packs to try first | Verified presets |
|---|---|---|
| Sub / clean bass | Olbaid Bass Utopia, SH-1 Floor Shakers, Mobile Tuned 808 Bass | Deep Sense, Underground Pillow, Low Blow, Simple Things, Round Hit; 808 Clean, 808 Punched |
| Growl / dubstep / reese | SeamlessR Monsters, Olbaid Bass Utopia, Black Octopus Pandora | Growling Machine, Wobble Trouble, Uber Wooble; Monster Raging/Savage/Warpig, Neuro Reece 1-9; SeamlessR: Abysscorpion, Colossal Mecha, Digitalzilla, Laserage, Mutant Reese ... |
| Supersaw / chords | Black Octopus Pandora, Sense Gemini Magnificence, Saif Sameer Fulcrum | Supersaw Nation, Big Saws, Fat Saws, Swell Chords, Wobble Chords 1-4, Saturn Sawtooths, Afterglow |
| Pluck / lead | Mobile Synth Pluck, Black Octopus Pandora, Arksun Cityscape | Synpluck Glass, Synpluck Crystal, Synpluck Musicbox, Synpluck Saw; Solar Pluck, Chill Lead, Digiharp; White Pluck, Laser Harp |
| Piano / keys | Essential Pianos, Black Octopus Pandora | Steinway D, Grand Piano, Yamaha C7, Bosendorfer, Rhodes MK1, Electric Piano, Pianopad; Softy EP 1/2, Nebula Keys |
| Pads / strings | Essential Strings, Black Octopus Pandora | All Strings Slow, All Strings Sustain, Violins Sustain, Cellos Pizzicato; Lush Strings, Superwarm Strings, Heaven, Interstellar |
| Guitars / bass guitar | Essential Guitars, Essential Bass Guitars | Chill Guitar, Nylon Shimmer, Muted Strat 1-3, Ovation Elite Plus |
| Synthwave / retro | Saif Sameer Synthwave, Analog Excellence | (list with fl_flex_select_pack) |
| Techno / electronica | Melodic Techno, Histibe Electronica, Phonon Collider | (list with fl_flex_select_pack) |
| Winds / GM fallback | Essential Winds, General Midi Library | (list with fl_flex_select_pack) |
| Drums in FLEX | Drumful Treasure | (the template's 808 sample channels are usually simpler) |

Full pack order (alphabetical = FLEX Library order): Analog Excellence, Arksun Cityscape,
Black Octopus Atlantis, Black Octopus Pandora, Drumful Treasure, Essential Bass Guitars,
Essential Guitars, Essential Pianos, Essential Strings, Essential Winds, General Midi Library,
Histibe Electronica, Melodic Techno, Mobile Synth Pluck, Mobile Tuned 808 Bass, Olbaid Bass Utopia,
Olbaid Compendium, Phonon Collider, Saif Sameer Fulcrum, Saif Sameer Synthwave, SeamlessR Monsters,
Sense Gemini Magnificence, SH-1 Floor Shakers, SH-1 Jump Up Repertoire, Sonitus Obscura,
Synthesizer Science.

## Notes

- Selecting a pack doesn't load a preset; `fl_flex_load_preset` does (and verifies by name).
- A cloned channel starts with the source's sound and name + "#2"; FLEX renames it to the
  preset once one loads.
- Drum sample channels (808 Kick etc.) ignore pitch mostly -- write pitch 60.
- Pitch range sanity: sub/bass roots MIDI 28-45, chords 54-81, leads 64-88. FL shows MIDI 60 as "C5".

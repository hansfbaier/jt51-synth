# jt51-synth

FPGA synth based on https://github.com/jotego/jt51
which implements a YM2151 chip.

USB2.0 High Speed MIDI Interface for super low latency,  optical ADAT outputs.
More coming soon.

Before using this repository, be sure to initialize the git submodules:

$ git submodule init

$ git submodule update

## Status
Basic monophonic playability over MIDI on one voice
python VGM music player script over MIDI sysex works
Currently only tested working with the QMTech EP4CE15 platform.

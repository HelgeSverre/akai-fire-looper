"""CC numbers from Behringer's JT-4000 MICRO Quick Start Guide, pp. 52–53.

https://mediadl.musictribe.com/media/PLM/data/docs/0722-ABR/QSG_BE_0722-ABR_JT-4000-MICRO_WW.pdf
Values are raw MIDI 0–127; the manual does not specify physical-unit curves.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Parameter:
    name: str
    cc: int


PAGES = (
    (
        "FILTER",
        (
            Parameter("Cutoff", 74),
            Parameter("Reso", 71),
            Parameter("Mod", 1),
            Parameter("Porta", 5),
        ),
    ),
    (
        "AMP ENV",
        (
            Parameter("Attack", 81),
            Parameter("Decay", 82),
            Parameter("Sustain", 83),
            Parameter("Release", 84),
        ),
    ),
    (
        "FILTER ENV",
        (
            Parameter("Attack", 85),
            Parameter("Decay", 86),
            Parameter("Sustain", 87),
            Parameter("Release", 88),
        ),
    ),
    (
        "LFO",
        (
            Parameter("LFO1 Amt", 70),
            Parameter("LFO1 Rate", 72),
            Parameter("LFO2 Amt", 28),
            Parameter("LFO2 Rate", 73),
        ),
    ),
)
PARAMETERS = {parameter.cc: parameter for _, page in PAGES for parameter in page}

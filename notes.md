```
F0 – System Exclusive
47 – Akai Manufacturer ID (see the MMA site for a list)
7F – The All-Call address
43 – Fire Sub-ID
65 – Write Pad Array command
hh – High length byte, bits 7 through 13 of following payload
ll – Low length byte, bits 0 through 7 of following payload
Repeat for pads you want to change {…
ii – Pad index, 00 top left through 3F bottom right
rr – Red level, 00 through 7F
gg – Green level, 00 through 7F
bb – Blue level, 00 through 7F
...}
F7 – End of Exclusive

```
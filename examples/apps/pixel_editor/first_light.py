"""Tutorial checkpoint: queued pad toggles, one LED batch and an OLED count."""

from queue import Empty, SimpleQueue

from akai_fire import get_akai_fire
from akai_fire_framework import AkaiFireApp


class FirstLight(AkaiFireApp):
    def on_init(self):
        self.presses: SimpleQueue[int] = SimpleQueue()
        self.lit: set[int] = set()

    def on_pad_press(self, pad, velocity):
        self.presses.put(pad)

    def on_button_press(self, button, event):
        if button == self.fire.BUTTON_STOP and event == "press":
            self.quit()

    def on_start(self):
        self.fire.clear_all()

    def on_update(self, dt):
        changed = False
        for _ in range(64):
            try:
                pad = self.presses.get_nowait()
            except Empty:
                break
            self.lit.symmetric_difference_update({pad})
            changed = True
        if changed:
            self.fire.set_multiple_pad_colors(
                [(pad, 0, 100 if pad in self.lit else 0, 0) for pad in range(64)]
            )
        self.canvas.draw_page(
            "First light", [f"Lit pads: {len(self.lit)}", "STOP to exit"]
        )


if __name__ == "__main__":
    with get_akai_fire(use_mock="pygame") as fire, FirstLight(fire) as app:
        app.run()

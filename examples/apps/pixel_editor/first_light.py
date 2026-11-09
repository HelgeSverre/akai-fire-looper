"""Tutorial checkpoint: foreground pad handlers and a shared OLED count."""

from akai_fire import get_akai_fire
from akai_fire.constants import BUTTON_STOP
from akai_fire_framework import AkaiFireApp, on


class FirstLight(AkaiFireApp):
    def on_init(self):
        self.lit: set[int] = set()
        self.dirty = True

    @on.pad()
    def toggle(self, event):
        self.lit.symmetric_difference_update({event.pad})
        self.dirty = True

    @on.button(BUTTON_STOP)
    def stop(self, event):
        self.quit()

    def on_start(self):
        self.fire.clear_all()

    def on_update(self, dt):
        if self.dirty:
            self.fire.set_multiple_pad_colors(
                [(pad, 0, 100 if pad in self.lit else 0, 0) for pad in range(64)]
            )
            self.dirty = False
        self.canvas.draw_page(
            "First light", [f"Lit pads: {len(self.lit)}", "STOP to exit"]
        )


if __name__ == "__main__":
    with get_akai_fire(use_mock="pygame") as fire, FirstLight(fire) as app:
        app.run()

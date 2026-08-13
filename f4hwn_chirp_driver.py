# CHIRP Driver Module for Quansheng UV-K5 / UV-K1 (F4HWN / Custom Firmware)
# Save this file and load it in CHIRP: Help -> Load Module from File...

from chirp import directory
try:
    from chirp.drivers import uvk5
except ImportError:
    import uvk5

@directory.register
class F4HWN_UVK5(uvk5.UVK5Radio):
    VENDOR = "Quansheng"
    MODEL = "UV-K5 (F4HWN Custom)"

    def sync_in(self):
        super().sync_in()
        # Remove read-only lock caused by custom firmware version strings
        self.is_read_only = False

    def validate(self):
        # Override validation to allow custom firmware image loading
        return True

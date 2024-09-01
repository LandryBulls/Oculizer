from PyDMXControl.profiles.defaults import Fixture

class Strobe(Fixture):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._register_channel('dimmer')
        self._register_channel_aliases('dimmer', 'brightness', 'dim', 'd')
        self._register_channel('strobe')
        self._register_channel_aliases('strobe', 's')
        self._register_channel('function')
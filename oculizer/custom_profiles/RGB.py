from PyDMXControl.profiles.defaults import Fixture

class RGB(Fixture):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._register_channel('dimmer')
        self._register_channel_aliases('dimmer', 'brightness', 'dim', 'd')
        self._register_channel('red')
        self._register_channel_aliases('red', 'r')
        self._register_channel('green')
        self._register_channel_aliases('green', 'g')
        self._register_channel('blue')
        self._register_channel_aliases('blue', 'b')
        self._register_channel('strobe')
        self._register_channel_aliases('strobe', 's')
        self._register_channel('function')

    def set_color(self, color):
        if color == 'red':
            self.set_channels(self.get_channels()[0], 255, 0, 0)
        elif color == 'orange':
            self.set_channels(self.get_channels()[0], 255, 127, 0)
        elif color == 'yellow':
            self.set_channels(self.get_channels()[0], 255, 255, 0)
        elif color == 'green':
            self.set_channels(self.get_channels()[0], 0, 255, 0)
        elif color == 'blue':
            self.set_channels(self.get_channels()[0], 0, 0, 255)
        elif color == 'purple':
            self.set_channels(self.get_channels()[0], 75, 0, 130)
        elif color == 'pink':
            self.set_channels(self.get_channels()[0], 255, 0, 255)
        elif color == 'white':
            self.set_channels(self.get_channels()[0], 255, 255, 255)
        else:
            raise ValueError(f"Color '{color}' not found")

    def set_strobe(self, speed, brightness):
        self.set_channels(255, 255, 255, speed, brightness, 0, 0)

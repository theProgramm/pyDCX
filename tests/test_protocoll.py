from unittest import TestCase

from app.ultradrive import protocoll


class TestDevice(TestCase):
    def test_search(self):
        self.assertEqual(protocoll.search(), b'\xF0\x00\x20\x32\x20\x0E\x40\xF7')

    def test_ping(self):
        self.assertEqual(protocoll.ping(0), b'\xF0\x00\x20\x32\x00\x0E\x44\xF7')
        self.assertEqual(protocoll.ping(1), b'\xF0\x00\x20\x32\x01\x0E\x44\xF7')
        self.assertEqual(protocoll.ping(15), b'\xF0\x00\x20\x32\x0f\x0E\x44\xF7')

    def test_dump(self):
        self.assertEqual(protocoll.dump(0, 0), b'\xF0\x00\x20\x32\x00\x0E\x50\x01\x00\x00\xF7')
        self.assertEqual(protocoll.dump(0, 1), b'\xF0\x00\x20\x32\x00\x0E\x50\x01\x00\x01\xF7')
        self.assertEqual(protocoll.dump(1, 0), b'\xF0\x00\x20\x32\x01\x0E\x50\x01\x00\x00\xF7')
        self.assertEqual(protocoll.dump(1, 1), b'\xF0\x00\x20\x32\x01\x0E\x50\x01\x00\x01\xF7')
        self.assertEqual(protocoll.dump(15, 0), b'\xF0\x00\x20\x32\x0f\x0E\x50\x01\x00\x00\xF7')
        self.assertEqual(protocoll.dump(15, 1), b'\xF0\x00\x20\x32\x0f\x0E\x50\x01\x00\x01\xF7')

    def test_set_transmit_mode(self):
        self.assertEqual(protocoll.set_transmit_mode(0), b'\xf0\x00\x20\x32\x00\x0e\x3F\x0c\x00\xf7',
                         "set transmit mode")
        self.assertEqual(protocoll.set_transmit_mode(1), b'\xf0\x00\x20\x32\x01\x0e\x3F\x0c\x00\xf7',
                         "set transmit mode")
        self.assertEqual(protocoll.set_transmit_mode(15), b'\xf0\x00\x20\x32\x0f\x0e\x3F\x0c\x00\xf7',
                         "set transmit mode")

    def test_params_smoke_test(self):
        command = protocoll.DirectCommand()
        command.add_param(protocoll.set_muted_param(1, True))
        command.add_param(protocoll.set_muted_param(1, False))
        command.add_param(protocoll.set_muted_param(0xa, True))
        command.add_param(protocoll.set_muted_param(0xa, False))
        command.add_param(protocoll.set_volume_param(1, -15))
        command.add_param(protocoll.set_volume_param(3, -3))
        command.add_param(protocoll.set_volume_param(5, 0))
        command.add_param(protocoll.set_volume_param(8, 3))
        command.add_param(protocoll.set_volume_param(0xa, 15))
        command.add_param(protocoll.set_limiter_on_param(1, True))
        command.add_param(protocoll.set_limiter_on_param(1, False))
        command.add_param(protocoll.set_limiter_on_param(0xA, True))
        command.add_param(protocoll.set_limiter_on_param(0xA, False))
        command.add_param(protocoll.set_limiter_threshold_param(1, -24))
        command.add_param(protocoll.set_limiter_threshold_param(0xA, 0))

        expected: bytes = b'\xF0\x00\x20\x32\x00\x0E\x20\x0F' \
                          + b'\x01\x03\x00\x01' \
                          + b'\x01\x03\x00\x00' \
                          + b'\x0A\x03\x00\x01' \
                          + b'\x0A\x03\x00\x00' \
                          + b'\x01\x02\x00\x00' \
                          + b'\x03\x02\x00x' \
                          + b'\x05\x02\x01\x16' \
                          + b'\x08\x02\x014' \
                          + b'\x0A\x02\x02,' \
                          + b'\x01\x46\x00\x01' \
                          + b'\x01\x46\x00\x00' \
                          + b'\x0A\x46\x00\x01' \
                          + b'\x0A\x46\x00\x00' \
                          + b'\x01\x47\x00\x00' \
                          + b'\x0A\x47\x01p' \
                          + b'\xf7'
        self.assertEqual(command.as_bytes(0), expected)

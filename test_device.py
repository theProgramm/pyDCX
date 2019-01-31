import logging
from logging import Logger
from unittest import TestCase

import Ultradrive


class TestDevice(TestCase):
    def test_patch_buffer(self):
        u = Ultradrive.Ultadrive(Logger("foo", logging.DEBUG))
        u.device(0).update_from_outgoing_command("")
        self.fail()

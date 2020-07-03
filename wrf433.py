#! /usr/bin/python3
from __future__ import division, print_function, unicode_literals

class TracerVar(object):
    def __init__(self, tracer, dut, name, *args, **kwargs):
        self.tracer = tracer
        self.var = self.tracer.register_var(dut, name, *args, **kwargs)

    def __call__(self, timestamp, value):
        self.tracer.change(self.var, timestamp, value)

class Tracer(object):
    """Write trace to a VCD file"""

    def __init__(self, f):
        from vcd import VCDWriter
        self.writer = VCDWriter(f, timescale = '1 us', date = 'today')
        self.t0 = None

    def add(self, dut, name, *args, **kwargs):
        return TracerVar(self, dut, name, *args, **kwargs)

    def register_var(self, dut, name, *args, **kwargs):
        return self.writer.register_var(dut, name, *args, **kwargs)

    def change(self, var, timestamp, value):
        if not timestamp:
            return

        timestamp = int(timestamp * 1E6)
        if self.t0 is None:
            self.t0 = timestamp
        self.writer.change(var, timestamp - self.t0, value)

class DummyTracer(object):
    def add(self, dut, name, *args, **kwargs):
        return lambda timestamp, value: None

tracer = DummyTracer()

class BaseDecoder(object):
    """Base decoder with helper functions for decoding RF protocols"""

    def __init__(self, timebase):
        self.verbose = 0
        self.lo_fuzz = 0.7
        self.hi_fuzz = 1.3
        self.last_timestamp = 0
        self.timebase = timebase

    def log(self, level, s, *args, **kwargs):
        name = self.__class__.__name__
        if level <= self.verbose:
            print(name + ": " + s, *args, **kwargs)

    def around(self, duration, expected):
        return (duration > expected * self.lo_fuzz and
                duration < expected * self.hi_fuzz)

    def duration(self, timestamp):
        duration = (timestamp - self.last_timestamp) / self.timebase
        self.last_timestamp = timestamp
        return duration

class ArcDecoder(BaseDecoder):
    """ARC Technology protocol used by Nexa/Proove

    http://tech.jolowe.se/old-home-automation-rf-protocols/"""

    def __init__(self, callback, timebase = 350E-6):
        super(ArcDecoder, self).__init__(timebase)
        self.verbose = 1
        self.callback = callback

        self.tracer_raw = tracer.add(self.__class__.__name__, 'raw', 'integer', size = 1)
        self.tracer_count = tracer.add(self.__class__.__name__, 'count', 'integer', size = 8)

        self.pos = 0
        self.neg = 0
        self.reset()

    def receive(self, timestamp, level):
        duration = self.duration(timestamp)

        # Save the duration of positive pulses and return
        if not level:
            self.pos = duration
            return

        if self.pos is None:
            return

        # Process the signals when a negative pulse has been seen
        self.neg = duration

        self.log(4, "hi %.1f lo %.1f count %s" % (self.pos, self.neg, self.count))

        if self.around(self.pos, 1) and self.around(self.neg, 3):
            self.raw_receive(1)

        elif self.around(self.pos, 3) and self.around(self.neg, 1):
            self.raw_receive(0)

        elif self.around(self.pos, 1) and self.neg > (32 - 5):
            self.stop_receive()
            self.reset()

        else:
            self.reset()

    def reset(self):
        self.count = 0
        self.raw = 0

        self.tracer_raw(self.last_timestamp, 'x')
        self.tracer_count(self.last_timestamp, 0)

    def raw_receive(self, v):
        if self.count is not None:
            self.log(3, "raw bit %u count %u" % (v, self.count))
            self.raw = (self.raw << 1) | v
            self.count += 1

            self.tracer_raw(self.last_timestamp, v)
            self.tracer_count(self.last_timestamp, self.count)

    def stop_receive(self):
        if self.count is None:
            return

        if self.count >= 3:
            self.log(2, "raw bits 0x%06x %s" % (self.raw, bin(self.raw)))

        if self.count != 24:
            return

        bits = 0
        for i in range(12):
            v = (self.raw >> i*2) & 3
            if v == 2:
                bits |= (1<<i)
            elif v == 3:
                bits |= (0<<i)
            else:
                return

        self.decode(bits)

    def decode(self, bits):
        house = chr(ord('A') + ((((bits >> 11) & 1) << 0) |
                                    (((bits >> 10) & 1) << 1) |
                                    (((bits >>  9) & 1) << 2) |
                                    (((bits >>  8) & 1) << 3)))
        unit = 1 + ((((bits >>  7) & 1) << 0) |
                        (((bits >>  6) & 1) << 1) |
                        (((bits >>  5) & 1) << 2) |
                        (((bits >>  4) & 1) << 3))

        unique = "arc-%c%u" % (house, unit)

        state = (bits >> 0) & 1

        self.log(1, "%s bits 0x%03x house %s unit %s state %s" % (
            unique, bits, house, unit, state))

        d = {
            'decoder' : self.__class__.__name__,
            'timestamp' : self.last_timestamp,
            'unique' : unique,
            'bits' : bits,
            'house' : house,
            'unit' : unit,
            'values' : { 'state' : state },
            }

        self.callback(d)

class LearningCodeDecoder(BaseDecoder):
    """Learning code protocol used by Nexa/Proove units

    https://tech.jolowe.se/home-automation-rf-protocols/"""

    def __init__(self, callback, timebase = 250E-6):
        super(LearningCodeDecoder, self).__init__(timebase)
        self.verbose = 1
        self.callback = callback

        self.tracer_raw = tracer.add(self.__class__.__name__, 'raw', 'integer', size = 1)
        self.tracer_count = tracer.add(self.__class__.__name__, 'count', 'integer', size = 8)

        # My transmitters seem to be rather crappy, so increase the fuzz margins
        self.lo_fuzz = 0.5
        self.hi_fuzz = 1.5
        self.reset()
        self.pos = 0
        self.neg = 0

    def receive(self, timestamp, level):
        duration = self.duration(timestamp)

        # Save the duration of positive pulses and return
        if not level:
            self.pos = duration
            return

        if self.pos is None:
            return

        # Process the signals when a negative pulse has been seen
        self.neg = duration

        self.log(4, "hi %.1f lo %.1f count %s" % (self.pos, self.neg, self.count))

        if self.around(self.pos, 1 * 1.25) and self.around(self.neg, 1 * 1.25):
            self.raw_receive(1)

        elif self.around(self.pos, 1) and self.around(self.neg, 5):
            self.raw_receive(0)

        elif self.around(self.pos, 1) and self.around(self.neg, 10):
            self.sync_receive()

        elif self.around(self.pos, 1) and self.neg > (40 - 5):
            self.pause_receive()
            self.reset()

        else:
            self.reset()

    def reset(self):
        self.count = None

        self.tracer_raw(self.last_timestamp, 'x')
        self.tracer_count(self.last_timestamp, 'x')

    def raw_receive(self, v):
        if self.count is not None:
            self.log(3, "raw bit %u count %u" % (v, self.count))
            self.raw = (self.raw << 1) | v
            self.count += 1

            self.tracer_raw(self.last_timestamp, v)
            self.tracer_count(self.last_timestamp, self.count)

    def sync_receive(self):
        self.log(3, "sync")
        self.count = 0
        self.raw = 0

    def pause_receive(self):
        if self.count is None:
            return

        self.log(2, "%s raw bits 0x%016x %s" % (self.count, self.raw, bin(self.raw)))

        if self.count != 64:
            return

        bits = 0
        for i in range(32):
            v = (self.raw >> i*2) & 3
            if v == 1:
                bits |= 1<<i
            elif v == 2:
                bits |= 0<<i
            else:
                return None

        self.decode(bits)

    def decode(self, bits):
        device = (bits >> 6) & 0x3ffffff
        group = (bits >> 5) & 1
        state = (bits >> 4) & 1
        channel = (bits >> 2) & 3
        unit = (bits >> 0) & 3
        unique = "lc-%07x-%u-%u-%u" % (device, channel, group, unit)

        self.log(1, "%s bits 0x%03x device 0x%7x state %s group %u channel %u unit %u" % (
            unique, bits, device, state, group, channel, unit))

        d = {
            'decoder' : self.__class__.__name__,
            'timestamp' : self.last_timestamp,
            'unique' : unique,
            'bits' : bits,
            'device' : device,
            'group' : group,
            'channel' : channel,
            'unit' : unit,
            'values' : { 'state' : state },
            }

        self.callback(d)

class EsicDecoder(BaseDecoder):
    """Temperature/Humidity sensor from Esic

    http://ala-paavola.fi/jaakko/doku.php?id=wt450h

    The protocol is using differential manchester encoding

    https://en.wikipedia.org/wiki/Differential_Manchester_encoding
    with a bit time of 2ms per bit"""

    def __init__(self, callback, timebase = 1E-3):
        super(EsicDecoder, self).__init__(timebase)
        self.verbose = 2
        self.callback = callback

        self.tracer_raw = tracer.add(self.__class__.__name__, 'raw', 'integer', size = 1)
        self.tracer_count = tracer.add(self.__class__.__name__, 'count', 'integer', size = 8)

        self.reset()

    def receive(self, timestamp, level):
        duration = self.duration(timestamp)

        self.log(4, "duration %.1f level %u count %s" % (duration, level, self.count))

        if level and duration > 10:
            self.log(3, "idle")
            self.reset()

        elif self.around(duration, 1):
            self.log(3, "short level %u count %u" % (not level, self.count))
            self.raw_receive(not level)

        elif self.around(duration, 2):
            self.log(3, "long level %u count %u" % (not level, self.count))
            self.raw_receive(not level)
            self.raw_receive(not level)

        else:
            if duration >= 2 and self.count == 72:
                self.last_received()

            elif self.count > 4:
                self.log(3, "bad %u bits 0x%x %s" % (self.count, self.raw, bin(self.raw)))

            self.reset()

    def raw_receive(self, v):
        self.raw = (self.raw << 1) | v
        self.count += 1

        if self.count == 4:
            if self.raw == 0xa:
                self.log(3, "start")

            else:
                self.log(3, "bad start %u raw 0x%x %s" % (self.count, self.raw, bin(self.raw)))
                self.reset()

        elif self.count == 72:
            self.last_received()
            self.reset()

        elif self.count == 100:
            self.log(2, "timeout %u raw 0x%x %s" % (self.count, self.raw, bin(self.raw)))
            self.reset()

        self.tracer_raw(self.last_timestamp, v)
        self.tracer_count(self.last_timestamp, self.count)

    def reset(self):
        self.count = 0
        self.raw = 0

        self.tracer_raw(self.last_timestamp, 'x')
        self.tracer_count(self.last_timestamp, 'x')

    def last_received(self):
        bits = 0
        parity = 0
        for i in range(35, -1, -1):
            t = (self.raw >> (2*i)) & 7
            t2 = (t >> 2) & 1
            t1 = (t >> 1) & 1
            t0 = (t >> 0) & 1
            bits <<= 1
            if t1 == t2:
                self.log(2, "invalid differential manchester", i)
                return None
            if t0 != t1:
                bits |= 1
                parity ^= 1

        if parity:
            self.log(2, "parity error")
            return

        bits >>= 1

        self.decode(bits)

    def decode(self, bits):
        hc = (bits >> 27) & 0xf
        cc = (bits >> 25) & 0x3
        unknown = (bits >> 22) & 0x7 # Always contains 6
        humidity = (bits >> 15) & 0x7f
        temperature = ((bits >> 0) & 0x7fff) / 128 - 50

        unique = 'esic-%u' % hc

        self.log(1, "%s bits 0x%03x hc %u cc %u unknown %u humidity %u temperature %.3f" % (
            unique, bits, hc, cc, unknown, humidity, temperature))

        d = {
            'decoder' : self.__class__.__name__,
            'timestamp' : self.last_timestamp,
            'unique' : unique,
            'bits' : bits,
            'hc' : hc,
            'cc' : cc,
            'values' : { 'temperature' : temperature, 'humidity' : humidity },
            }

        self.callback(d)

class Mux(object):
    def __init__(self):
        self.decoders = []
        self.tracer_raw = tracer.add('rf', 'raw', 'integer', size = 1)

    def add_decoder(self, decoder):
        self.decoders.append(decoder)

    def receive(self, t, v):
        self.tracer_raw(t, v)
        for decoder in self.decoders:
            decoder.receive(t, v)

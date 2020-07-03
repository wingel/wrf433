#! /usr/bin/python3
from __future__ import division, print_function, unicode_literals

import os
import sys
import time
import select
import collections

import wrf433

def callback(d):
    print(d)

def main():
    pin = 27
    open('/sys/class/gpio/export', 'w').write('%u' % pin)
    open('/sys/class/gpio/gpio%u/direction' % pin, 'w').write('in')
    open('/sys/class/gpio/gpio%u/edge' % pin, 'w').write('both')
    fd = os.open('/sys/class/gpio/gpio%u/value' % pin, os.O_RDONLY)

    csv_fn = None
    if len(sys.argv) > 1:
        csv_fn = sys.argv[1]
        csv_data = collections.deque(maxlen = 100000)

    mux = wrf433.Mux()
    mux.add_decoder(wrf433.ArcDecoder(callback))
    mux.add_decoder(wrf433.LearningCodeDecoder(callback))
    mux.add_decoder(wrf433.EsicDecoder(callback))

    print("Receiving RF data from GPIO %d" % pin, file = sys.stderr)

    try:
        while True:
            i, o, e = select.select([], [], [fd], 0.1)
            t = time.time()

            if fd in e:
                os.lseek(fd, 0, os.SEEK_SET)
                s = os.read(fd, 10)
                s = s.strip()
                assert len(s) == 1
                v = int(chr(s[0]))

                if csv_fn:
                    csv_data.append((t, v))

                mux.receive(t, v)

    except KeyboardInterrupt:
        if csv_fn:
            print("Writing CSV to %s" % csv_fn)
            with open(csv_fn, 'w') as f:
                for t, v in csv_data:
                    f.write('%.6f,%u\n' % (t, v))

if __name__ == '__main__':
    main()

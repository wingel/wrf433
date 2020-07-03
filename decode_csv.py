#! /usr/bin/python3
from __future__ import division, print_function, unicode_literals

import sys
import wrf433

def callback(d):
    print(d)

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: %s csvfile [vcdfile]\n" % sys.argv[0])

    csv_fn = sys.argv[1]

    print("Decoding CSV from %s" % csv_fn, file = sys.stderr)

    vcd_f = None
    if len(sys.argv) >= 3:
        vcd_fn = sys.argv[2]
        vcd_f = open(vcd_fn, 'w')
        wrf433.tracer = wrf433.Tracer(vcd_f)
        print("Writing VCD trace to %s" % vcd_fn, file = sys.stderr)

    mux = wrf433.Mux()
    mux.add_decoder(wrf433.ArcDecoder(callback))
    mux.add_decoder(wrf433.LearningCodeDecoder(callback))
    mux.add_decoder(wrf433.EsicDecoder(callback))

    for l in open(csv_fn):
        parts = l.split(',')
        t = float(parts[0])
        v = int(parts[1])
        mux.receive(t, v)

    if vcd_f:
        vcd_f.close()

if __name__ == '__main__':
    main()

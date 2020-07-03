Wingel's 433MHz RF protocol decoder
===================================

This project is a decoder for a few 433MHz RF procols that are used
for a couple of products sold in Sweden.

I was planning to call this project "rf433", but that name was already
taken, so I just prepended my nickname (Wingel) to the name.

Supported Protocols
-------------------

Old Nexa/Proove protocol with switches for house and unit codes
New Nexa/Proove Learning Code protocol
Esic Temperature sensors (for example sold at Clas Ohlson)

How to use
==========

Well, to start with, buy a decent on off keying (OOK) 433MHz receiver.
I have had good success with a RXB6 receiver.  Connect VCC/5V and GND
from the module to the corresponding pins on the Pi.  Connect the DATA
output from the module to GPIO pin 17 on the Pi.  Here's an example in
Swedish of how to connect a receiver (and a transmitter):

 https://smartaguider.se/guide-styr-fjarrstrombrytare-med-raspberry-pi/

I can not recommend the really cheap receivers used above though.
It's wholly built with discrete components and in my experience the
modduple picks up too much noise to be useful.  Also, note that many
of discrete receivers have a 5V data output.  The Raspberry PI GPIO
pins exepect signals at 3.3V and are _not_ 5V tolerant.  This means
that which means that sooner or later feeding 5V into a 3.3V GPIO pin
will destroy the pin.

Copy rpi_decoder.py and wrf433.py to the Raspberry Pi.  Run the
receiver as root:

 sudo ./rpi_decoder.py

Press a button on a supported unit and you should see something like
this:

 {'decoder': 'ArcDecoder', 'timestamp': 1594046786.097191, 'unique': 'arc-E3', 'bits': 582, 'house': 'E', 'unit': 3, 'values': {'state': 0}}
 ArcDecoder: arc-E3 bits 0x246 house E unit 3 state 0

 LearningCodeDecoder: lc-10b3f6e-0-0-0 bits 0x42cfdb90 device 0x10b3f6e state 1 group 0 channel 0 unit 0
 {'decoder': 'LearningCodeDecoder', 'timestamp': 1594046787.098772, 'unique': 'lc-10b3f6e-0-0-0', 'bits': 1120918416, 'device': 17514350, 'group': 0, 'channel': 0, 'unit': 0, 'values': {'state': 1}}

 {'decoder': 'EsicDecoder', 'timestamp': 1594046785.734818, 'unique': 'esic-1', 'bits': 25964356621, 'hc': 1, 'cc': 1, 'values': {'temperature': 22.1015625, 'humidity': 49}}
 ArcDecoder: arc-E3 bits 0x246 house E unit 3 state 0

The first line of each group is a debug printout from the decoder
class itself.  The second line is a Python dictionary which can be
used for further processing.

It's also possible to use rpi_decoder.py to record the data signal to
a file.  Pass a filename to it and when you stop it with Ctrl-C it
will write the time and polarity of the last 100000 edges to the file:

 sudo ./rpi_decoder.py rf.csv

You can now decode the file offline.  This can be very useful when
developing a new decoder.  I'm sure there are bugs in the decoders, so
this is also a good way of debugging the code.

 ./decode_csv.py rf.csv

Finally, you can also use decode_csv.py to output the RF signal and
some internal state to a VCD file which can be visualised with
GTKWave.  First install some dependencies:

 sudo apt install python3-pip gtkwave
 sudo pip3 install pyvcd

Then run the offline decoder again, this time with the name of the VCD
file as the second parameter:

 ./decode_csv.py rf.csv rf.vcd

The VCD file can then be opened in GTKWave.

Internals
---------

wrf433.py mostly contains classes to decode each protocol.  The module
also contains a tracing functionality.  If the global variable
"tracer" has been initialized with an instance of the class Tracer
before instatiating the Mux or Decoders, some internal state will be
written to a ".vcd" file which can be visualised with GTKWave.

rpi_decoder.py is an example of how to use the decoder on a Raspberry
Pi.  It expects a 433MHz receiver to be connected to GPIO PIN 17.  Run
rpi_decoder.py as root and and it will decode all supported protocols
and print some information to standard output.  If a filename is
passed on the command line, it will also dump the time and polarity
for the last 100000 edges in CSV format to that file.

decode_csv.py can be used to decode data from a CSV dump and can write
a VCD file which can be viewed with GTKWave.  It's basically the same
code as rpi_decoder.py except that it reads RF data from a CSV file
and can set up a Tracer instance.

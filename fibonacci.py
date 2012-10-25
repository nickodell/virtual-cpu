#!/usr/bin/python
# This implements a fibonacci counter by creating a virtual CPU and loading a program.
# The CPU has 3 registers, A, B, and C, plus 16 banks of 16 bytes of memory
# R. Goldberg would be proud.
# -NJO 2012.10.24
from cpu import *

if __name__ == "__main__":
    c = CPU()
    c.program_from_string("""
note: programs can't contain capital letters/numbers in comments lest they be counted as code
setup
FB
E0 00
E1 01
here's where the loop begins
nop slide to make jump length calc easier
A0 A0 A0 A0 A0 A0 A0 A0 A0 A0 A0 A0 A0 A0 A0 A0 
add a to b, put in c
00
detect overflow and end program
C8 AF

move c to b to a back to c again
20 21
print number
F8 FA FB
loop end, jump back to beginning
BF""")
    c.run()

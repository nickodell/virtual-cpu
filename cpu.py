#!/usr/bin/python

import binascii
ux = binascii.unhexlify
hx = binascii.hexlify
import time
import re
import sys


### opcodes
### specified in hexidecimal
# 00 SUBTRACT A-B INTO C
# 01 SUBTRACT A-B INTO C, don't update flags
# 02 ADD A+B INTO C
# 03 ADD A+B INTO C, don't update flags
# 10 XOR A^B INTO C
# 11 AND A&B INTO C
# 12 OR  A|B INTO C
# 1A NOT A INTO A
# 1B NOT B INTO B
# 1C NOT C INTO C
# 20 SWAP A,B
# 21 SWAP B,C
# 22 SWAP C,A
# 3x BANK SELECT, x is bank
# 4x LOAD INTO A, from address x + (bank * 16)
# 5x LOAD INTO B, ...
# 6x LOAD INTO C, ...
# 7x STORE FROM A, ...
# 8x STORE FROM B, ...
# 9x STORE FROM C, ...
# Ax JUMP FORWARD x bytes. A0 is a NOP
# Bx JUMP BACKWARD x bytes. B0 is an infinite loop
# Cx BRANCH - JUMP FORWARD 1 IF CONDITION x, ELSE 2
# bit 0x08 inverts the conditional
#  Conditions:
#   0 ADD OVERFLOW FLAG
#   1 SUBTRACT OVERFLOW FLAG
#   2 A=B
#   3 B=C
#   4 C=A
#   5 A=0
#   6 B=0
#   7 C=0
#  
# Dx unused
# E0 LOAD CONSTANT INTO A, next byte is constant
# E1 LOAD CONSTANT INTO B, ...
# E2 LOAD CONSTANT INTO C, ...
#
# F0 ACCEPT INPUT INTO A, not implemented
# 
# F8 OUTPUT FROM A 
# F9 CHANGE BUFFER FROM UNSIGNED INTEGER TO ASCII DECIMAL INTEGER, not implemented
# FA TURN OFF OUTPUT BUFFER, FLUSH BUFFER
# FB TURN ON  OUTPUT BUFFER
# FC ERASE    OUTPUT BUFFER

register_lookup = {"A":0,"B":1,"C":2}

class CPU:
    memory = bytearray(256) # Note: I haven't tested main memory one bit
    registers = bytearray(3)
    flags = 0
    program = bytearray(1024)
    program_counter = 0
    opcodes = None # To be set up in __init__
    selected_bank = 0
    buffer_output_ = False
    buffer_ = bytes()
    
    def __init__(self):
        self.opcodes = (
            ("00", lambda: self.add(update_flags = 1)),
            ("01", lambda: self.add(update_flags = 0)),
            ("02", lambda: self.sub(update_flags = 1)),
            ("03", lambda: self.sub(update_flags = 0)),
            
            ("10", lambda: self.xor()),
            ("11", lambda: self.and_()),
            ("12", lambda: self.or_()),
            ("1A", lambda: self.not_(register = "A")),
            ("1B", lambda: self.not_(register = "B")),
            ("1C", lambda: self.not_(register = "C")),
            
            ("20", lambda: self.swap("A", "B")),
            ("21", lambda: self.swap("B", "C")),
            ("22", lambda: self.swap("C", "A")),
            
            ("3x", lambda: self.bank_select()),
            
            ("4x", lambda: self.load(register = "A")),
            ("5x", lambda: self.load(register = "B")),
            ("6x", lambda: self.load(register = "C")),
            
            ("7x", lambda: self.store(register = "A")),
            ("8x", lambda: self.store(register = "B")),
            ("9x", lambda: self.store(register = "C")),
            
            ("Ax", lambda: self.jump(direction = 1)),
            ("Bx", lambda: self.jump(direction = -1)),
            
            ("Cx", lambda: self.branch()),
            
            ("E0", lambda: self.load_constant(register = "A")),
            ("E1", lambda: self.load_constant(register = "B")),
            ("E2", lambda: self.load_constant(register = "C")),
            
            ("F0", lambda: self.accept_input()),
            
            ("F8", lambda: self.output(register = "A")),
            ("F9", lambda: self.binary_integer_to_ascii_integer()),
            ("FA", lambda: self.buffer_output(False)),
            ("FB", lambda: self.buffer_output(True)),
            ("FC", lambda: self.erase_buffer()),
        )
        self.load_opcodes()
    def load_opcodes(self):
        """This turns the useless tuple-based list into a dictionary
        indexed by byte. Also expands wildcards. Only expands one wildcard per instruction"""
        hexdigits = list("0123456789ABCDEF")
        result = {}
        for opcode in self.opcodes:
            if "x" not in opcode[0]:
                expanded = [opcode]
            else:
                op, function = opcode
                expanded = [(op.replace('x', hexdigit), function) for hexdigit in hexdigits]
            
            for op, function in expanded:
                result[ord(ux(op))] = function
        self.opcodes = result
    def program_from_string(self, string):
        """Interpret hex, ignore non hex and lowercase letters
        If too few instructions, fill out with A0"""
        string += "   " # Fix oddity with regex when no whitespace at end
        regex = '[0-9A-F]{2}\W'
        output = re.findall(regex, string)
        output = ''.join(map(lambda x: x.strip(), output))
        output = ux(output).ljust(1024, "\xA0")
        self.program[:] = output
        # print(hx(output))
    def do_step(self):
        op = self.get_next_instruction()
        self.instruction = op
        if op in self.opcodes:
            self.opcodes[op]()
        else:
            raise Exception(binascii.hexlify(chr(op)) + " is not a valid instruction!")
    def run(self):
        while True:
            self.do_step()
            #Slow it down so I can watch it, unless NOP
            time.sleep(0.1) if self.instruction != ord("\xA0") else None
    def get_next_instruction(self):
        try:
            temp = self.program[self.program_counter]
        except IndexError:
            if self.program_counter > 1023:
                print("Terminated.")
            else:
                print(str(self.program_counter) + " is not a valid program memory address!")
            sys.exit()
        self.program_counter += 1
        #print self.program_counter - 1, hx(chr(temp))
        return temp
        
    def get_register(self, register):
        value = self.registers[register_lookup[register]]
        #print "get_register:", register, value
        return value
    def set_register(self, register, value):
        #print "set_register:", register, value
        self.registers[register_lookup[register]] = value
        
    def set_flag(self, flag, value):
        if flag == "add_over":
            index = 0
        elif flag == "sub_over":
            index = 1
        else:
            raise Exception("Bad flag type " + flag + " - you should never see this")
        index = 1 << index
        self.flags = (self.flags | index) if value else (self.flags & (~index))
    def get_flag(self, flag):
        # Yeah yeah, code duplication. I know.
        if flag == "add_over":
            index = 0
        elif flag == "sub_over":
            index = 1
        else:
            raise Exception("Bad flag type " + flag + " - you should never see this")
        
        index = 1 << index
        return bool(self.flags & index)
        
    # Onto the instructions themselves!
    def add(self, update_flags):
        a = self.get_register("A")
        b = self.get_register("B")
        val = a + b
        trunc = val & 0xFF
        if update_flags:
            self.set_flag("add_over", val != trunc)
        self.set_register("C", trunc)
        #print "add: ", a, b, val, self.flags
    def sub(self, update_flags):
        a = self.get_register("A")
        b = self.get_register("B")
        val = a - b
        if val < 0:
            trunc = val + 256
        if update_flags:
            self.set_flag("sub_over", val != trunc)
        self.set_register("C", trunc)
    def xor(self):
        a = self.get_register("A")
        b = self.get_register("B")
        val = a ^ b
        self.set_register("C", val)
    def and_(self):
        a = self.get_register("A")
        b = self.get_register("B")
        val = a & b
        self.set_register("C", val)
    def or_(self):
        a = self.get_register("A")
        b = self.get_register("B")
        val = a | b
        self.set_register("C", val)
    def not_(self, register):
        temp = self.get_register(register)
        temp = ~temp & 0xFF
        self.set_register(register, temp)
    def swap(self, register1, register2):
        temp = self.get_register(register1)
        self.set_register(register1, self.get_register(register2))
        self.set_register(register2, temp)
    def bank_select(self):
        self.selected_bank = self.instruction & 0x0F
    def load(self, register):
        address = self.instruction & 0x0F
        address += self.selected_bank * 16
        value = memory[address]
        self.set_register(register, value)
    def store(self, register):
        address = self.instruction & 0x0F
        address += self.selected_bank * 16
        self.get_register(register, value)
        value = memory[address]
    def jump(self, direction):
        length = self.instruction & 0x0F
        self.program_counter += length * direction
        # quirk - A0 and B0 doing the same thing would be useless, so for direction of -1, we jump back one.
        if direction == -1:
            self.program_counter -= 1
    def branch(self):
        condition_index = self.instruction & 0x07
        condition_invert = bool(self.instruction & 0x08)
        conditions = [
            lambda: self.get_flag("add_over"),
            lambda: self.get_flag("sub_over"),
            lambda: self.get_register("A") == self.get_register("B"),
            lambda: self.get_register("B") == self.get_register("C"),
            lambda: self.get_register("C") == self.get_register("A"),
            lambda: self.get_register("A") == 0,
            lambda: self.get_register("B") == 0,
            lambda: self.get_register("C") == 0,
        ]
        condition = conditions[condition_index]
        if condition() != condition_invert:
            self.program_counter += 1
    def load_constant(self, register):
        self.set_register(register, self.get_next_instruction())
    def accept_input(self, register):
        raise NotImplementedError()
    def output(self, register):
        val = self.get_register(register)
        if self.buffer_output_:
            self.buffer_ += chr(val)
        else:
            print hx(val),
    def buffer_output(self, value):
        self.buffer_output_ = value
        if not value:
            # turning buffering off, flush buffer
            print hx(self.buffer_)
            self.erase_buffer()
    def binary_integer_to_ascii_integer(self):
        raise NotImplementedError()
    def erase_buffer(self):
        self.buffer_ = bytes()



"""
Operation E.D.I.T.H. v5 — FridayVM Assembler & Bytecode Compiler
Document Ref: SPEC-ACT1-FRIDAYVM

Compiles human-readable FridayVM assembly into bytecode for embedding
in StarkEmployeePortal.exe. The bytecode uses the DEFAULT opcode mapping
(instruction_id == opcode_byte). The VM interpreter shuffles these at
runtime using the dynamic seed.

Also includes a reference disassembler and emulator for testing.
"""
import struct
import sys
import os
import binascii
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.crypto import generate_opcode_map, lcg_next
from backend.app.config import FRIDAYVM_SEED, MACHINE_GUID, BUILD_EPOCH, EMPLOYEE_SECRET


# ══════════════════════════════════════════════════════════
# ISA Definition (SPEC-ACT1-FRIDAYVM §3)
# ══════════════════════════════════════════════════════════

# Instruction ID -> (mnemonic, operand_sizes_in_bytes)
ISA = {
    0:  ("HALT",    []),
    1:  ("LOAD",    [1, 4]),       # reg(1), val(4)
    2:  ("STORE",   [1, 2]),       # reg(1), addr(2)
    3:  ("PUSH",    [1]),          # reg(1)
    4:  ("POP",     [1]),          # reg(1)
    5:  ("ADD",     [1, 1]),       # r_dest(1), r_src(1)
    6:  ("SUB",     [1, 1]),       # r_dest(1), r_src(1)
    7:  ("XOR",     [1, 1]),       # r_dest(1), r_src(1)
    8:  ("CMP",     [1, 1]),       # r1(1), r2(1)
    9:  ("JMP",     [2]),          # offset(2, signed)
    10: ("JZ",      [2]),          # offset(2, signed)
    11: ("JNZ",     [2]),          # offset(2, signed)
    12: ("SYSCALL", [1]),          # call_id(1)
    13: ("ROL",     [1, 1]),       # reg(1), val(1)
    14: ("SWAP",    [1, 1]),       # r1(1), r2(1)
    15: ("MOD",     [1, 1]),       # r_dest(1), r_src(1)
}

# Reverse: mnemonic -> instruction_id
MNEMONIC_TO_ID = {v[0]: k for k, v in ISA.items()}


# ══════════════════════════════════════════════════════════
# Assembler
# ══════════════════════════════════════════════════════════

def assemble(source: str) -> bytes:
    """Assemble FridayVM source text into bytecode (default opcode mapping)."""
    bytecode = bytearray()

    for line_num, line in enumerate(source.strip().split("\n"), 1):
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue

        # Strip inline comments (everything after ';')
        if ";" in line:
            line = line[:line.index(";")].strip()
        if not line:
            continue

        parts = line.replace(",", " ").split()
        mnemonic = parts[0].upper()

        if mnemonic not in MNEMONIC_TO_ID:
            raise ValueError(f"Line {line_num}: Unknown mnemonic '{mnemonic}'")

        instr_id = MNEMONIC_TO_ID[mnemonic]
        operand_sizes = ISA[instr_id][1]

        if len(parts) - 1 != len(operand_sizes):
            raise ValueError(
                f"Line {line_num}: {mnemonic} expects {len(operand_sizes)} operands, "
                f"got {len(parts) - 1}"
            )

        # Write opcode byte (= instruction ID in default mapping)
        bytecode.append(instr_id)

        # Write operands
        for i, size in enumerate(operand_sizes):
            val_str = parts[i + 1].strip()
            # Parse register references like R0, R1
            if val_str.upper().startswith("R"):
                val = int(val_str[1:])
            elif val_str.startswith("0x") or val_str.startswith("0X"):
                val = int(val_str, 16)
            else:
                val = int(val_str)

            if size == 1:
                bytecode.append(val & 0xFF)
            elif size == 2:
                bytecode.extend(struct.pack("<h", val))  # signed 16-bit
            elif size == 4:
                bytecode.extend(struct.pack("<I", val))  # unsigned 32-bit

    return bytes(bytecode)


# ══════════════════════════════════════════════════════════
# Disassembler
# ══════════════════════════════════════════════════════════

def disassemble(bytecode: bytes, opcode_map: dict | None = None) -> str:
    """Disassemble bytecode into human-readable assembly.
    If opcode_map is provided, translates shuffled opcodes back.
    """
    if opcode_map is None:
        opcode_map = {i: i for i in range(32)}

    output = []
    pc = 0

    while pc < len(bytecode):
        raw_opcode = bytecode[pc]
        if raw_opcode >= 32:
            output.append(f"0x{pc:04X}: DB 0x{raw_opcode:02X}  ; unknown")
            pc += 1
            continue

        instr_id = opcode_map.get(raw_opcode, -1)
        if instr_id not in ISA:
            output.append(f"0x{pc:04X}: DB 0x{raw_opcode:02X}  ; junk opcode (ID={instr_id})")
            pc += 1
            continue

        mnemonic, operand_sizes = ISA[instr_id]
        pc += 1
        operands = []

        for size in operand_sizes:
            if pc + size > len(bytecode):
                output.append(f"  ; TRUNCATED at 0x{pc:04X}")
                return "\n".join(output)

            if size == 1:
                val = bytecode[pc]
                operands.append(f"0x{val:02X}")
            elif size == 2:
                val = struct.unpack_from("<h", bytecode, pc)[0]
                operands.append(f"0x{val:04X}")
            elif size == 4:
                val = struct.unpack_from("<I", bytecode, pc)[0]
                operands.append(f"0x{val:08X}")
            pc += size

        line = f"0x{pc - 1 - sum(operand_sizes):04X}: {mnemonic}"
        if operands:
            line += " " + ", ".join(operands)
        output.append(line)

    return "\n".join(output)


# ══════════════════════════════════════════════════════════
# Emulator (for verification)
# ══════════════════════════════════════════════════════════

class FridayVMEmulator:
    """Reference emulator for FridayVM bytecode."""

    def __init__(self, bytecode: bytes, opcode_map: dict | None = None):
        self.bytecode = bytearray(bytecode)
        self.registers = [0] * 8
        self.pc = 0
        self.sp = 0
        self.flags = 0  # bit 0 = ZF, bit 1 = SF
        self.stack = [0] * 256
        self.memory = bytearray(1024)
        self.opcode_map = opcode_map or {i: i for i in range(32)}
        self.halted = False
        self.input_buffer = []
        self.output_buffer = []

    def _update_flags(self, result: int):
        self.flags = 0
        if (result & 0xFFFFFFFF) == 0:
            self.flags |= 1  # ZF
        if result < 0:
            self.flags |= 2  # SF

    @property
    def zf(self) -> bool:
        return bool(self.flags & 1)

    def step(self) -> bool:
        """Execute one instruction. Returns False if halted."""
        if self.halted or self.pc >= len(self.bytecode):
            return False

        raw_opcode = self.bytecode[self.pc]
        instr_id = self.opcode_map.get(raw_opcode % 32, -1)
        self.pc += 1

        if instr_id == 0:  # HALT
            self.halted = True
            return False
        elif instr_id == 1:  # LOAD reg, val
            reg = self.bytecode[self.pc]; self.pc += 1
            val = struct.unpack_from("<I", self.bytecode, self.pc)[0]; self.pc += 4
            self.registers[reg] = val
        elif instr_id == 2:  # STORE reg, addr
            reg = self.bytecode[self.pc]; self.pc += 1
            addr = struct.unpack_from("<H", self.bytecode, self.pc)[0]; self.pc += 2
            val = self.registers[reg]
            struct.pack_into("<I", self.memory, addr, val)
        elif instr_id == 3:  # PUSH reg
            reg = self.bytecode[self.pc]; self.pc += 1
            self.stack[self.sp] = self.registers[reg]
            self.sp += 1
        elif instr_id == 4:  # POP reg
            reg = self.bytecode[self.pc]; self.pc += 1
            self.sp -= 1
            self.registers[reg] = self.stack[self.sp]
        elif instr_id == 5:  # ADD r_dest, r_src
            rd = self.bytecode[self.pc]; self.pc += 1
            rs = self.bytecode[self.pc]; self.pc += 1
            result = self.registers[rd] + self.registers[rs]
            self.registers[rd] = result & 0xFFFFFFFF
            self._update_flags(result)
        elif instr_id == 6:  # SUB r_dest, r_src
            rd = self.bytecode[self.pc]; self.pc += 1
            rs = self.bytecode[self.pc]; self.pc += 1
            result = self.registers[rd] - self.registers[rs]
            self.registers[rd] = result & 0xFFFFFFFF
            self._update_flags(result)
        elif instr_id == 7:  # XOR r_dest, r_src
            rd = self.bytecode[self.pc]; self.pc += 1
            rs = self.bytecode[self.pc]; self.pc += 1
            result = self.registers[rd] ^ self.registers[rs]
            self.registers[rd] = result & 0xFFFFFFFF
            self._update_flags(result)
        elif instr_id == 8:  # CMP r1, r2
            r1 = self.bytecode[self.pc]; self.pc += 1
            r2 = self.bytecode[self.pc]; self.pc += 1
            result = self.registers[r1] - self.registers[r2]
            self._update_flags(result)
        elif instr_id == 9:  # JMP offset
            offset = struct.unpack_from("<h", self.bytecode, self.pc)[0]; self.pc += 2
            self.pc += offset
        elif instr_id == 10:  # JZ offset
            offset = struct.unpack_from("<h", self.bytecode, self.pc)[0]; self.pc += 2
            if self.zf:
                self.pc += offset
        elif instr_id == 11:  # JNZ offset
            offset = struct.unpack_from("<h", self.bytecode, self.pc)[0]; self.pc += 2
            if not self.zf:
                self.pc += offset
        elif instr_id == 12:  # SYSCALL call_id
            call_id = self.bytecode[self.pc]; self.pc += 1
            if call_id == 0x01:  # Read input
                if self.input_buffer:
                    self.registers[0] = ord(self.input_buffer.pop(0))
                else:
                    self.registers[0] = 0
            elif call_id == 0x02:  # Write output
                self.output_buffer.append(chr(self.registers[0] & 0xFF))
        elif instr_id == 13:  # ROL reg, val
            reg = self.bytecode[self.pc]; self.pc += 1
            val = self.bytecode[self.pc]; self.pc += 1
            r = self.registers[reg]
            self.registers[reg] = ((r << val) | (r >> (32 - val))) & 0xFFFFFFFF
        elif instr_id == 14:  # SWAP r1, r2
            r1 = self.bytecode[self.pc]; self.pc += 1
            r2 = self.bytecode[self.pc]; self.pc += 1
            self.registers[r1], self.registers[r2] = self.registers[r2], self.registers[r1]
        elif instr_id == 15:  # MOD r_dest, r_src
            rd = self.bytecode[self.pc]; self.pc += 1
            rs = self.bytecode[self.pc]; self.pc += 1
            if self.registers[rs] != 0:
                self.registers[rd] = self.registers[rd] % self.registers[rs]
            self._update_flags(self.registers[rd])
        else:
            # Unknown instruction — skip
            pass

        return True

    def run(self, max_steps: int = 10000):
        """Run until HALT or max_steps."""
        steps = 0
        while self.step() and steps < max_steps:
            steps += 1
        return steps


def main():
    """Demo: assemble, disassemble, and emulate a simple program."""
    # Simple test program: load values, add, compare
    source = """
    ; Load test values
    LOAD R0 0x53    ; 'S' = 83
    LOAD R1 0x54    ; 'T' = 84
    LOAD R2 0x41    ; 'A' = 65
    ; Add R0 and R1 -> R0
    ADD R0 R1
    ; Store result
    STORE R0 0x0000
    ; Halt
    HALT
    """

    bytecode = assemble(source)
    print(f"Assembled {len(bytecode)} bytes of bytecode")
    print(f"Hex: {bytecode.hex()}")

    print("\n--- Disassembly (default mapping) ---")
    print(disassemble(bytecode))

    print("\n--- Disassembly (shuffled mapping) ---")
    shuffled = generate_opcode_map(FRIDAYVM_SEED)
    print(f"Seed: {hex(FRIDAYVM_SEED)}")

    # To disassemble shuffled bytecode, we need the inverse map
    inverse_map = {v: k for k, v in shuffled.items()}
    # Note: the bytecode was assembled with default mapping,
    # so disassembling with default map shows correct instructions

    print("\n--- Emulation ---")
    vm = FridayVMEmulator(bytecode)
    steps = vm.run()
    print(f"Executed {steps} steps")
    print(f"R0 = {vm.registers[0]} (0x{vm.registers[0]:08X})")
    print(f"R1 = {vm.registers[1]} (0x{vm.registers[1]:08X})")
    print(f"R2 = {vm.registers[2]} (0x{vm.registers[2]:08X})")
    print(f"Memory[0:4] = {vm.memory[0:4].hex()}")

    # Verify: R0 should be 83 + 84 = 167 (0xA7)
    assert vm.registers[0] == 167, f"Expected 167, got {vm.registers[0]}"
    print("\n[+] FridayVM emulation verification PASSED")

    # Show employee secret for reference
    print(f"\n[+] Employee Secret: {EMPLOYEE_SECRET.hex()}")


if __name__ == "__main__":
    main()

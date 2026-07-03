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
    16: ("NOP",     []),           # No operation (padding)
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
        self.current_page = 0  # Page track for self-modifying code

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

        # Self-modifying page boundaries logic (SPEC-ACT1-FRIDAYVM §4)
        new_page = self.pc // 16
        if new_page != self.current_page:
            old_p = self.current_page
            r0_val = self.registers[0] & 0xFF
            r1_val = self.registers[1] & 0xFF

            # Encrypt old 16-byte page with R0
            for idx in range(old_p * 16, min((old_p + 1) * 16, len(self.bytecode))):
                self.bytecode[idx] ^= r0_val
            
            # Decrypt new 16-byte page with R1
            for idx in range(new_page * 16, min((new_page + 1) * 16, len(self.bytecode))):
                self.bytecode[idx] ^= r1_val

            self.current_page = new_page

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
        elif instr_id == 16:  # NOP
            # No operation — just continue
            pass
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
    """CLI utility for FridayVM assembly, disassembly, and execution."""
    if len(sys.argv) < 3:
        print("Usage:")
        print(f"  {sys.argv[0]} assemble <source.asm> <output.bin>")
        print(f"  {sys.argv[0]} disassemble <bytecode.bin> [seed_hex_or_int]")
        print(f"  {sys.argv[0]} run <bytecode.bin> [seed_hex_or_int]")
        print(f"  {sys.argv[0]} run-trace <bytecode.bin> [seed_hex_or_int]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    target_path = sys.argv[2]

    # Parse optional seed
    seed = None
    if len(sys.argv) > 3:
        seed_str = sys.argv[3]
        if seed_str.lower().startswith("0x"):
            seed = int(seed_str, 16)
        else:
            seed = int(seed_str)

    opcode_map = None
    if seed is not None:
        opcode_map = generate_opcode_map(seed)

    if cmd == "assemble":
        out_path = sys.argv[3] if len(sys.argv) > 3 else "output.bin"
        with open(target_path, "r") as f:
            source = f.read()
        bytecode = assemble(source)
        with open(out_path, "wb") as f:
            f.write(bytecode)
        print(f"[+] Assembled to {out_path} ({len(bytecode)} bytes)")

    elif cmd == "disassemble":
        with open(target_path, "rb") as f:
            bytecode = f.read()
        
        # Invert mapping if provided
        inv_map = None
        if opcode_map is not None:
            inv_map = {v: k for k, v in opcode_map.items()}

        print(disassemble(bytecode, inv_map))

    elif cmd == "run" or cmd == "run-trace":
        with open(target_path, "rb") as f:
            bytecode = f.read()
        
        inv_map = None
        if opcode_map is not None:
            inv_map = {v: k for k, v in opcode_map.items()}

        vm = FridayVMEmulator(bytecode, inv_map)
        
        steps = 0
        max_steps = 5000
        while not vm.halted and steps < max_steps:
            if cmd == "run-trace":
                # Print register and state before step
                regs = " ".join(f"R{i}={vm.registers[i]:08X}" for i in range(8))
                pc_prefix = f"PC={vm.pc:04X} Page={vm.current_page} {regs}"
                
                # Fetch next instruction mnemonic
                if vm.pc < len(vm.bytecode):
                    raw_op = vm.bytecode[vm.pc]
                    instr_id = vm.opcode_map.get(raw_op % 32, -1)
                    mnemonic = ISA.get(instr_id, ("DB", []))[0]
                    print(f"[{pc_prefix}] Executing: {mnemonic}")
                else:
                    print(f"[{pc_prefix}] Execution past boundary")
            
            if not vm.step():
                break
            steps += 1

        print(f"\n[+] VM execution finished in {steps} steps.")
        print(f"    Registers: " + " ".join(f"R{i}={vm.registers[i]:08X}" for i in range(8)))
        print(f"    Flags: ZF={1 if vm.zf else 0}")
        if vm.output_buffer:
            print(f"    Output Buffer: {''.join(vm.output_buffer)}")



if __name__ == "__main__":
    main()

"""
    riscv_asm
    ~~~~~~~~~

    A small riscv assembler
"""
from functools import partial
import operator
import os

def assemble(org, program, out_file="a.out"):
    while True:
        block = []
        errors = []
        if program.encode(org, block, None, errors):
            break

    if len(errors) > 0:
        for fmt, info in errors:
            print fmt.format(*info)
    else:
        with open(out_file, "wb") as fd:
            fd.write("".join(block))
        os.chmod(out_file, 0755)

class Group(object):
    def __init__(self, body=None):
        self.body = [] if body is None else body
        self.org = 0
    
    def encode(self, org, block, group, errors):
        ready = (self.org == org + len(block))
        self.org = org + len(block)
        for encoder in self.body:
            subready = encoder.encode(org, block, self, errors)
            ready = ready and subready
        return ready

class Encoder(object):
    def __init__(self, fn, values):
        self.fn = fn
        self.values = values

    def encode(self, org, block, group, errors):
        return self.fn(org, block, group, errors, self.values)

class Op(object):
    def __init__(self, fn, *args):
        self.fn = fn
        self.args = args

def resolve(org, arg):
    if isinstance(arg, Group):
        return arg.org
    elif isinstance(arg, Op):
        return arg.fn(*(resolve(org, arg) for arg in arg.args))
    elif arg is here:
        return org
    else:
        return arg

here = object()

def bytes(*args):
    return Encoder(enc_bytes, args)

def halfs(*args):
    return Encoder(enc_halfs, args)

def words(*args):
    return Encoder(enc_words, args)

def quads(*args):
    return Encoder(enc_quads, args)

def string(arg):
    return Encoder(enc_string, arg)

def check_size(size):
    return Encoder(enc_check_size, size)

def check(errors, condition, fmt, *info):
    if not condition:
        errors.append((fmt, info))

def enc_bytes(org, block, group, errors, args):
    for a in args:
        a = resolve(org + len(block), a)
        check(errors, 0 <= a <= 0xFF, "bytes {}", hex(a))
        block.append(chr(a))
    return True

def enc_halfs(org, block, group, errors, args):
    for a in args:
        a = resolve(org + len(block), a)
        check(errors, 0 <= a <= 0xFFFF, "halfs {}", hex(a))
        block.append(chr((a >> 0) & 255))
        block.append(chr((a >> 8) & 255))
    return True

def enc_words(org, block, group, errors, args):
    for a in args:
        a = resolve(org + len(block), a)
        check(errors, 0 <= a <= 0xFFFFFFFF, "words {}", hex(a))
        block.append(chr((a >>  0) & 255))
        block.append(chr((a >>  8) & 255))
        block.append(chr((a >> 16) & 255))
        block.append(chr((a >> 24) & 255))
    return True

def enc_quads(org, block, group, errors, args):
    for a in args:
        a = resolve(org + len(block), a)
        check(errors, 0 <= a <= 0xFFFFFFFFFFFFFFFF, "quads {}", hex(a))
        block.append(chr((a >>  0) & 255))
        block.append(chr((a >>  8) & 255))
        block.append(chr((a >> 16) & 255))
        block.append(chr((a >> 24) & 255))
        block.append(chr((a >> 32) & 255))
        block.append(chr((a >> 40) & 255))
        block.append(chr((a >> 48) & 255))
        block.append(chr((a >> 56) & 255))
    return True

def enc_string(org, block, group, errors, string):
    block.extend(string.encode('utf-8'))
    return True

def enc_check_size(org, block, group, errors, size):
    real_sz = org + len(block) - resolve(org + len(block), group)
    sz = resolve(org + len(block), size)
    check(errors, real_sz == sz, "size mismatch {} != {}", real_sz, sz)
    return True

# Can be used to gauge if you got it right.
def str_template(template):
    vector = bin(template)[2:34].rjust(32, '0')
    return " ".join([
        vector[0:7], vector[7:12], vector[12:17],
        vector[17:20], vector[20:25], vector[25:]])
    return vector

class I32Enc(object):
    def __init__(self, template, fn, *values):
        self.template = template
        self.fn = fn
        self.values = values

    def encode(self, org, block, group, errors):
        a = self.template | self.fn(org, block, group, errors, self.values)
        block.append(chr((a >>  0) & 255))
        block.append(chr((a >>  8) & 255))
        block.append(chr((a >> 16) & 255))
        block.append(chr((a >> 24) & 255))
        return True

def r_type(org, block, group, errors, (rd, rs1, rs2)):
    assert 0 <= rd < 32
    assert 0 <= rs1 < 32
    assert 0 <= rs2 < 32
    return (rd << 7) | (rs1 << 15) | (rs2 << 20)

def fence_type(org, block, group, (prec, succ)):
    imm = (prec & 0xF) << 4 | (succ & 0xF)
    return i_type(org, block, group, (0, 0, imm))

def i_type(org, block, group, errors, (rd, rs1, imm)):
    assert 0 <= rd < 32
    assert 0 <= rs1 < 32
    imm = resolve(org + len(block), imm)
    check(errors, -2048 <= imm < 2048, "imm field (i_type) {}", imm)
    return (rd << 7) | (rs1 << 15) | (imm << 20)

def s_type(org, block, group, errors, (rs1, rs2, imm)):
    assert 0 <= rs1 < 32
    assert 0 <= rs2 < 32
    imm = resolve(org + len(block), imm)
    check(errors, -2048 <= imm < 2048, "imm field (s_type) {}", imm)
    low = (imm & 31)
    return (low << 7) | (rs1 << 15) | (rs2 << 20) | ((imm >> 5) << 25)

def b_type(org, block, group, errors, (rs1, rs2, imm)):
    assert 0 <= rs1 < 32
    assert 0 <= rs2 < 32
    imm = resolve(org + len(block), imm) - (org + len(block))
    check(errors, -4096 <= imm < 4096, "imm field (b_type) {}", imm)
    assert imm & 1 == 0
    low = (imm & 31) | ((imm >> 11) & 1)
    high = (imm >> 5) & 63
    sign = ((imm >> 12) & 1)
    return (low << 7) | (rs1 << 15) | (rs2 << 20) | (high << 25) | (sign << 31)

def u_type(org, block, group, errors, (rd, imm)):
    assert 0 <= rd < 32
    imm = resolve(org + len(block), imm)
    assert (imm >> 12) << 12 == imm
    return (rd | imm) << 7

def j_type(org, block, group, errors, (rd, imm)):
    assert 0 <= rd < 32
    imm = resolve(org + len(block), imm) - (org + len(block))
    check(errors, -1048576 <= imm < 1048576, "imm field (j_type) {}", imm)
    assert imm & 1 == 0
    sign = ((imm >> 20) & 1)
    high = imm & 2047 | ((imm >> 11) & 1)
    low  = (imm >> 12) & 255
    return (rd << 7) | (high << 25) | (sign << 31)

def calc_hi(value):
    if value > 0 and value & 2048 != 0:
        value = value + 4096
    if value < 0 and value & 2048 != 0:
        value = value + 4096
    return value ^ (value & 4095)

def calc_lo(value):
    k = value & 4095
    if k >= 2048:
        return ~(~k & 4095)
    return k

hi = partial(Op, calc_hi)
lo = partial(Op, calc_lo)

# Self-check for hi/lo calculators.
for x in range(-10000, 10000):
    assert calc_hi(x) + calc_lo(x) == x

def lli(rd, imm):
    rel = Group()
    offset = Op(operator.sub, imm, rel)
    rel.body.extend([
        auipc(rd, hi(offset)),
        addi(rd, rd, lo(offset)) ])
    return rel

lui   = partial(I32Enc, 0x37, u_type)
auipc = partial(I32Enc, 0x17, u_type)
jal  = partial(I32Enc, 0x6F, j_type)
jalr = partial(I32Enc, 0x67, i_type)
beq  = partial(I32Enc, 0x0063, b_type)
bne  = partial(I32Enc, 0x1063, b_type)
blt  = partial(I32Enc, 0x4063, b_type)
bge  = partial(I32Enc, 0x5063, b_type)
bltu = partial(I32Enc, 0x6063, b_type)
bgeu = partial(I32Enc, 0x7063, b_type)
lb  = partial(I32Enc, 0x0003, i_type)
lh  = partial(I32Enc, 0x1003, i_type)
lw  = partial(I32Enc, 0x2003, i_type)
lbu = partial(I32Enc, 0x4003, i_type)
lhu = partial(I32Enc, 0x5003, i_type)
sb = partial(I32Enc, 0x0023, s_type)
sh = partial(I32Enc, 0x1023, s_type)
sw = partial(I32Enc, 0x2023, s_type)
addi  = partial(I32Enc, 0x0013, i_type)
slti  = partial(I32Enc, 0x2013, i_type)
sltiu = partial(I32Enc, 0x3013, i_type)
xori  = partial(I32Enc, 0x4013, i_type)
ori   = partial(I32Enc, 0x6013, i_type)
andi  = partial(I32Enc, 0x7013, i_type)

slli  = partial(I32Enc, 0x00001013, r_type)
srli  = partial(I32Enc, 0x00005013, r_type)
srai  = partial(I32Enc, 0x40005013, r_type)
add   = partial(I32Enc, 0x00000033, r_type)
sub   = partial(I32Enc, 0x40000033, r_type)
sll   = partial(I32Enc, 0x00001033, r_type)
slt   = partial(I32Enc, 0x00002033, r_type)
sltu  = partial(I32Enc, 0x00003033, r_type)
xor   = partial(I32Enc, 0x00004033, r_type)
srl   = partial(I32Enc, 0x00005033, r_type)
sra   = partial(I32Enc, 0x40005033, r_type)
or_   = partial(I32Enc, 0x00006033, r_type)
and_  = partial(I32Enc, 0x00007033, r_type)
fence   = partial(I32Enc, 0x000F, fence_type)
fence_i = words(0x100F)
ecall  = words(0x000073)
ebreak = words(0x100073)

csrrw  = partial(I32Enc, 0x1073, i_type)
csrrs  = partial(I32Enc, 0x2073, i_type)
csrrc  = partial(I32Enc, 0x3073, i_type)
csrrwi = partial(I32Enc, 0x5073, i_type)
csrrsi = partial(I32Enc, 0x6073, i_type)
csrrci = partial(I32Enc, 0x7073, i_type)

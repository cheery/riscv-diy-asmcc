from riscv_asm import *

load_address = 0x010000
_start = Group()
file_end = Group()
ehdr = Group()
phdr = Group()

ehdr.body.extend([
    bytes(0x7f, 0x45, 0x4c, 0x46, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    halfs(2, 0xf3),                         # e_type, e_machine
    words(1),                               # e_version
    quads(_start),                          # e_entry
    quads(Op(operator.sub, phdr, ehdr)),    # e_phoff
    quads(0),                               # e_shoff
    words(0),                               # e_flags
    halfs(64, 56),                          # e_ehsize, e_phentsize
    halfs(1, 0, 0, 0),                      # e_phnum
    check_size(64)])                        # e_shentsize (64)
                                            # e_shnum
                                            # e_shstrndx

file_size = Op(operator.sub, file_end, load_address)
phdr.body.extend([
    words(1, 5),                            # p_type, p_flags
    quads(0),                               # p_offset
    quads(load_address, load_address),      # p_vaddr, p_paddr           
    quads(file_size, file_size),            # p_filesz
    quads(0x1000),                          # p_align
    check_size(56)])                         

# Linux system call numbers https://rv8.io/syscalls.html
sys_write = 64
sys_exit  = 93
# Standard fileno numbers
stdin  = 0
stdout = 1
stderr = 2

greeting_text_str = "Hello world\n"
greeting_text_len = len(greeting_text_str)
greeting_text = Group([string(greeting_text_str)])

success = Group([
    addi(10, 0, 0),
    addi(17, 0, sys_exit),
    ecall ])

failure = Group([
    addi(10, 0, 1),
    addi(17, 0, sys_exit),
    ecall ])

program = Group([
    ehdr,
    phdr,
    _start,
    addi(10, 0, stdout),
    lli(11, greeting_text),
    addi(12, 0, greeting_text_len),
    addi(17, 0, sys_write),
    ecall,
    bne(10, 12, failure),
    success,
    failure,
    greeting_text,
    file_end])

assemble(load_address, program, "hello")

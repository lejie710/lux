# Lux guest loader. It stands in for an operating system loader.
#
# What it does, in order:
#   1. prints one line through the firmware console (boot services still active);
#   2. asks the firmware for the memory map;
#   3. calls ExitBootServices, the moment firmware hands the machine over;
#   4. reports what it saw over the serial port, by raw port I/O, because the
#      firmware console is gone after step 3;
#   5. prints a FINAL MARKER line and idles forever (interrupts off, halt).
#
# It never powers off and never ends the virtual machine. The recorder on the
# host ends the run, so the software TPM is still alive to be read.
#
# The bytes of this program are measured by the firmware. Changing any
# instruction or string here changes the loader's digest and with it TPM
# register 4 in every recording. Comments do not matter.
#
# Build:  as -o loader.o loader.s
#         ld -m i386pep --subsystem 10 -e efi_main --no-insert-timestamp -o loader.efi loader.o
    .intel_syntax noprefix
    .text
    .globl efi_main
efi_main:
    sub     rsp, 0x48
    mov     [rip+image], rcx
    mov     [rip+systab], rdx
    mov     rcx, [rdx+64]              # SystemTable->ConOut
    lea     rdx, [rip+msg_start]
    call    [rcx+8]                    # ConOut->OutputString
    mov     r12, 2                     # at most two attempts
retry:
    mov     rax, [rip+systab]
    mov     rbx, [rax+96]              # SystemTable->BootServices
    mov     qword ptr [rip+mapsize], 32768
    lea     rcx, [rip+mapsize]
    lea     rdx, [rip+mapbuf]
    lea     r8,  [rip+mapkey]
    lea     r9,  [rip+descsize]
    lea     rax, [rip+descver]
    mov     [rsp+32], rax
    call    [rbx+56]                   # BootServices->GetMemoryMap
    mov     [rip+gmm_status], rax
    test    rax, rax
    jnz     report
    mov     rcx, [rip+image]
    mov     rdx, [rip+mapkey]
    call    [rbx+232]                  # BootServices->ExitBootServices
    mov     [rip+ebs_status], rax
    test    rax, rax
    jz      report
    dec     r12
    jnz     retry
report:
    cld
    lea     rsi, [rip+s_gmm]
    call    puts
    mov     rax, [rip+gmm_status]
    call    puthex64
    lea     rsi, [rip+s_ebs]
    call    puts
    mov     rax, [rip+ebs_status]
    call    puthex64
    lea     rsi, [rip+s_mapsize]
    call    puts
    mov     rax, [rip+mapsize]
    call    puthex64
    lea     rsi, [rip+s_descsize]
    call    puts
    mov     rax, [rip+descsize]
    call    puthex64
    lea     rsi, [rip+s_mapkey]
    call    puts
    mov     rax, [rip+mapkey]
    call    puthex64
    mov     rax, [rip+systab]
    mov     r13, [rax+104]             # NumberOfTableEntries
    mov     r14, [rax+112]             # ConfigurationTable
    lea     rsi, [rip+s_ncfg]
    call    puts
    mov     rax, r13
    call    puthex64
cfgloop:
    test    r13, r13
    jz      memmap
    lea     rsi, [rip+s_cfg]
    call    puts
    xor     r15, r15
guidloop:
    mov     al, [r14+r15]
    call    puthex8
    inc     r15
    cmp     r15, 16
    jb      guidloop
    mov     al, ' '
    call    putc
    mov     rax, [r14+16]
    call    puthex64
    add     r14, 24
    dec     r13
    jmp     cfgloop
memmap:
    cmp     qword ptr [rip+gmm_status], 0
    jne     done
    lea     r13, [rip+mapbuf]
    mov     r14, r13
    add     r14, [rip+mapsize]
mmloop:
    cmp     r13, r14
    jae     done
    lea     rsi, [rip+s_mm]
    call    puts
    mov     eax, [r13]                 # Type
    call    puthex64
    mov     al, ' '
    call    putc
    mov     rax, [r13+8]               # PhysicalStart
    call    puthex64
    mov     al, ' '
    call    putc
    mov     rax, [r13+24]              # NumberOfPages
    call    puthex64
    mov     al, ' '
    call    putc
    mov     rax, [r13+32]              # Attribute
    call    puthex64
    add     r13, [rip+descsize]
    jmp     mmloop
done:
    lea     rsi, [rip+s_done]
    call    puts
idle:                                   # the run is ended from outside by the recorder
    cli
    hlt
    jmp     idle

putc:                                   # al = character
    push    rax
    mov     dx, 0x3fd
1:  in      al, dx
    test    al, 0x20
    jz      1b
    pop     rax
    mov     dx, 0x3f8
    out     dx, al
    ret
puts:                                   # rsi = zero-terminated ASCII
1:  lodsb
    test    al, al
    jz      2f
    call    putc
    jmp     1b
2:  ret
nib:
    cmp     al, 10
    jb      1f
    add     al, 7
1:  add     al, 0x30
    jmp     putc
puthex8:                                # al = byte
    push    rax
    shr     al, 4
    call    nib
    pop     rax
    and     al, 15
    jmp     nib
puthex64:                               # rax = value
    mov     r8, rax
    mov     ecx, 8
1:  rol     r8, 8
    mov     al, r8b
    call    puthex8
    dec     ecx
    jnz     1b
    ret

    .data
    .balign 8
anchor:     .quad efi_main              # one absolute address, so the linker emits a relocation table
image:      .quad 0
systab:     .quad 0
mapsize:    .quad 0
mapkey:     .quad 0
descsize:   .quad 0
descver:    .quad 0
gmm_status: .quad 0xffffffffffffffff
ebs_status: .quad 0xffffffffffffffff
msg_start:  .string16 "LUX-LOADER A: started, boot services active\r\n"
s_gmm:      .asciz "\r\nLUX GetMemoryMap status="
s_ebs:      .asciz "\r\nLUX ExitBootServices status="
s_mapsize:  .asciz "\r\nLUX MemoryMapSize="
s_descsize: .asciz "\r\nLUX DescriptorSize="
s_mapkey:   .asciz "\r\nLUX MapKey="
s_ncfg:     .asciz "\r\nLUX ConfigTableEntries="
s_cfg:      .asciz "\r\nLUX CFG "
s_mm:       .asciz "\r\nLUX MM "
s_done:     .asciz "\r\nLUX-FINAL-MARKER loader idle after ExitBootServices\r\n"
    .balign 16
mapbuf:     .fill 32768, 1, 0

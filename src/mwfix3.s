; MWFIX 3.0 - add-on appended to MouseWrite's MW.SYSTEM ($2000-$3E18).
; MW.SYSTEM's JMP at $2000 now comes here ($3E1A).  This stub copies the
; body (mwbody.s, assembled for $1000) down to $1000 and runs it, because the
; body's splash screen needs hi-res page 2 ($4000-$5FFF), which the stub's own
; load address would overlap.  The body then jumps to MW.SYSTEM's real start, $2046.
        .org $3E19
        .byte $00       ; $3E19 is copied by MW.SYSTEM's own relocation; keep it 0
mover:  lda #<body
        sta $06
        lda #>body
        sta $07
        lda #$00
        sta $08
        lda #$10
        sta $09
        ldx #>(bodyend - body + 255)
        ldy #0
@l:     lda ($06),y
        sta ($08),y
        iny
        bne @l
        inc $07
        inc $09
        dex
        bne @l
        jmp $1000
body:   .incbin "mwbody.bin"
bodyend:

; o6patch.s - appended to MouseWrite's MW.O6 overlay (which ends at $6F3F).
; MW.O6 holds Merge Paragraphs/Lists; its entry $6CB6 is patched to JMP detour.
; File > Export ODT is dispatched through the same overlay stub as Merge, so
; the detour checks which File item was chosen ($4FCE = menu id, $4FCF = item, from MouseText ToolKit MenuSelect).
; For Export ODT it loads MW.OD with MouseWrite's own overlay loader ($6162).
; MW.OD is built so that the return address of that JSR lands on a JMP into
; the exporter, and so that MW.OD's own "JSR $6162" (reloading MW.O6 when the
; export is done) returns onto the RTS here - back to MouseWrite's dispatcher.
        .setcpu "65C02"
        .org $6F40
detour: lda $4FCE
        cmp #$10        ; File menu?
        bne merge
        lda $4FCF
        cmp #$09        ; item 9 = Export ODT
        bne merge
        lda #<odname
        ldy #>odname
        ldx odname
        jmp far
merge:  bit $03AA       ; the instruction replaced at $6CB6
        jmp $6CB9
odname: .byte 5, "MW.OD"
        ; The JSR that loads MW.OD sits at the end of the overlay window, so that
        ; MW.OD can be one contiguous block with its two fixed entries at the end.
        .res $7938 - *, 0
far:    jsr $6162       ; load MW.OD over this overlay...
landing:
        jmp $0832       ; ...which continues here in MW.OD (this copy only runs if it couldn't load)
reload: jsr $6162       ; MW.OD's copy of this reloads MW.O6...
done:   rts             ; ...and returns here, to MouseWrite's menu dispatcher
        .export landing, reload, done

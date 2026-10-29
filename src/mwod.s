; MW.OD - File > Export ODT for MouseWrite 3.0
;
; An overlay: MouseWrite's loader reads it into the overlay window at
; $6949-$7948, in place of MW.O6 (see o6patch.s for how it gets called and
; how control returns).  It writes the open document as an OpenDocument Text
; file NAME.ODT next to the document's own file, then shows the result with
; MouseWrite's alert routine and reloads MW.O6.
;
; The document is read straight from auxiliary memory, so unsaved changes are
; included: rows of <width> bytes ($0346, the right margin) from aux $0900 up
; to the end pointer in the text engine's (auxiliary) zero page, $1A/$1B.
;
; The conversion is exactly the one in tools/mw2odt.py, and the static ZIP and
; XML pieces come from tools/make_odt_inc.py (mwod.inc).
;
; Memory used while it runs (all free during a menu command):
;   $8B00-$8EFF  ProDOS file buffer (MouseWrite's own, no file is open)
;   $495C-$4BD9  MouseWrite's alert-text buffer (refilled by every alert):
;                output buffer, row buffer, output pathname
;   $06-$25, $3C-$43 of zero page: saved on entry and restored before returning

        .setcpu "65C02"
        .macpack longbranch

MLI     = $BF00
AUXMOVE = $C311
ALERT   = $1340         ; A/Y = message
LOADOVL = $6162         ; MouseWrite's overlay loader, A/Y/X = name, length
O6NAME  = $5FD7         ; "mw.o6" (counted string in MW.UI)
TITLE   = $52D9         ; pointer to the window title: the document's counted
UNTITLD = $5303         ;   full pathname, or this "Untitled" string
WIDTH   = $0346         ; document right margin = row width
FLAGS   = $03AA         ; bit 7: a document is open
IOBUF   = $8B00
OBUF    = $495C         ; 256-byte output buffer
ROW     = $4A5C         ; one document row (up to 128)
OUTPATH = $4ADC         ; counted output pathname (up to 64 + 1)
fix     = $4B1E         ; 12: CRC and sizes of content.xml
cdoff   = $4B2A         ; 3: central directory offset
ntmp_lo = $4B2D
ntmp_hi = $4B2E
savezp  = $4B30         ; 32: zero page $06-$25
savezp2 = $4B50         ; 8: zero page $3C-$43

LANDING = $793B         ; from o6patch.s
RELOAD  = $793E

src     = $06           ; aux address of the next row
dend    = $08           ; aux address of the end of the text
crc     = $0A           ; 4 bytes
size    = $0E           ; 3 bytes
obi     = $11           ; output buffer index
ptr     = $12
ptr2    = $14
pend    = $16           ; spaces waiting to be written
inpara  = $17
dirty   = $18           ; styles changed since the spans were written
opened  = $19           ; spans open in the output
skip    = $1A           ; skipping a custom-font row
nextq   = $1B           ; next paragraph starts a new page
pstyle  = $1C           ; 'P', 'Q' (new page) or 'F' (footnote)
on      = $1D           ; style bits B U I K S D N W
colour  = $1E           ; 0 or $13-$18
last    = $1F           ; last byte written
width   = $20
hy      = $21           ; row ends in a hyphenated word
werr    = $22           ; first ProDOS error while streaming
tmp     = $23
yy      = $24
ntmp    = $25           ; the character being written

        .org $6949
        .incbin "MW.O6", 0, $A9         ; the overlay stub table, identical in every overlay

; ------------------------------------------------------------------ main
export: sei
        ldx #$1F
@sv:    lda $06,x
        sta savezp,x
        dex
        bpl @sv
        ldx #7
@sv2:   lda $3C,x
        sta savezp2,x
        dex
        bpl @sv2

        bit FLAGS
        bmi @open
        lda #<msg_nodoc
        ldy #>msg_nodoc
        jmp finish
@open:  lda TITLE
        sta ptr
        lda TITLE+1
        sta ptr+1
        cmp #>UNTITLD
        bne @named
        lda ptr
        cmp #<UNTITLD
        bne @named
        lda #<msg_untitled
        ldy #>msg_untitled
        jmp finish
@named: jsr makepath
        bcc @pathok
        lda #<msg_name
        ldy #>msg_name
        jmp finish
@pathok:
        jsr MLI                 ; DESTROY an older export (error ignored)
        .byte $C1
        .word p_destroy
        jsr MLI
        .byte $C0               ; CREATE
        .word p_create
        jcs @err
        jsr MLI
        .byte $C8               ; OPEN
        .word p_open
        jcs @err
        lda p_open+5
        sta p_write+1
        sta p_mark+1
        sta p_close+1

        jsr rawwrite_static1    ; mimetype + manifest + content.xml header
        jcs @errc

        lda #$FF                ; content.xml, streamed
        sta crc
        sta crc+1
        sta crc+2
        sta crc+3
        stz size
        stz size+1
        stz size+2
        stz obi
        stz werr
        lda #<prologue
        ldy #>prologue
        jsr emit_s
        jsr convert
        lda #<epilogue
        ldy #>epilogue
        jsr emit_s
        jsr flush
        lda werr
        jne @errc

        ldx #3                  ; final CRC and sizes into the fix-up record
@cf:    lda crc,x
        eor #$FF
        sta fix,x
        dex
        bpl @cf
        lda size
        sta fix+4
        sta fix+8
        lda size+1
        sta fix+5
        sta fix+9
        lda size+2
        sta fix+6
        sta fix+10
        stz fix+7               ; sizes are 32 bits (fix lives in a buffer of spaces)
        stz fix+11

        jsr MLI
        .byte $CF               ; GET_MARK = central directory offset
        .word p_mark
        jcs @errc
        ldx #11
@ct:    lda fix,x
        sta tail+CD3_FIX,x
        dex
        bpl @ct
        ldx #2
@eo:    lda p_mark+2,x
        sta tail+EOCD_OFF,x
        sta cdoff,x
        dex
        bpl @eo

        lda #<H3_FIX            ; patch the content.xml local header
        sta p_mark+2
        lda #>H3_FIX
        sta p_mark+3
        stz p_mark+4
        jsr MLI
        .byte $CE
        .word p_mark
        jcs @errc
        jsr rawwrite_fix
        jcs @errc
        ldx #2
@bk:    lda cdoff,x
        sta p_mark+2,x
        dex
        bpl @bk
        jsr MLI
        .byte $CE
        .word p_mark
        jcs @errc
        jsr rawwrite_tail
        jcs @errc
        jsr MLI
        .byte $CC
        .word p_close
        jcs @err
        jsr okmsg
        lda #<msgbuf
        ldy #>msgbuf
        jmp finish

@errc:  pha
        jsr MLI
        .byte $CC
        .word p_close
        pla
@err:   jsr hex
        stx msg_err_hex
        sty msg_err_hex+1
        lda #<msg_err
        ldy #>msg_err
        ; fall through

; finish: A/Y = message.  Restore zero page, show it, reload MW.O6, return.
finish: sta ntmp_lo
        sty ntmp_hi
        ldx #$1F
@rs:    lda savezp,x
        sta $06,x
        dex
        bpl @rs
        ldx #7
@rs2:   lda savezp2,x
        sta $3C,x
        dex
        bpl @rs2
        cli
        lda ntmp_lo
        ldy ntmp_hi
        jsr ALERT
        lda #<O6NAME
        ldy #>O6NAME
        ldx O6NAME
        jmp RELOAD

; ------------------------------------------------------------------ writing
rawwrite_static1:
        lda #<static1
        sta p_write+2
        lda #>static1
        sta p_write+3
        lda #<STATIC1_LEN
        sta p_write+4
        lda #>STATIC1_LEN
        sta p_write+5
        bra rw
rawwrite_fix:
        lda #<fix
        sta p_write+2
        lda #>fix
        sta p_write+3
        lda #12
        sta p_write+4
        stz p_write+5
        bra rw
rawwrite_tail:
        lda #<tail
        sta p_write+2
        lda #>tail
        sta p_write+3
        lda #<TAIL_LEN
        sta p_write+4
        lda #>TAIL_LEN
        sta p_write+5
rw:     jsr MLI
        .byte $CB
        .word p_write
        rts

; flush: write what is in the output buffer
flush:  lda obi
        beq @x
        sta p_write+4
        stz p_write+5
        bra wbuf
@x:     rts
wfull:  stz p_write+4               ; 256 bytes
        lda #1
        sta p_write+5
wbuf:   lda #<OBUF
        sta p_write+2
        lda #>OBUF
        sta p_write+3
        jsr MLI
        .byte $CB
        .word p_write
        bcc @ok
        ldx werr
        bne @ok
        sta werr
@ok:    rts

; emit: A = one byte of content.xml.  Keeps X and Y.
emit:   sta last
        phx
        phy
        pha
        eor crc
        sta crc
        jsr nib
        jsr nib
        pla
        ldy obi
        sta OBUF,y
        inc obi
        bne @nf
        jsr wfull
@nf:    inc size
        bne @x
        inc size+1
        bne @x
        inc size+2
@x:     ply
        plx
        rts
nib:    lda crc                     ; CRC-32, four bits at a time
        and #$0F
        tax
        ldy #4
@s:     lsr crc+3
        ror crc+2
        ror crc+1
        ror crc
        dey
        bne @s
        lda crc
        eor crct0,x
        sta crc
        lda crc+1
        eor crct1,x
        sta crc+1
        lda crc+2
        eor crct2,x
        sta crc+2
        lda crc+3
        eor crct3,x
        sta crc+3
        rts

; emit_s: A/Y = zero-terminated string; bytes $01-$1F are dictionary phrases
emit_s: sta ptr
        sty ptr+1
@l:     lda (ptr)
        beq @done
        cmp #$20
        bcs @plain
        tax
        lda dict_lo-1,x
        sta ptr2
        lda dict_hi-1,x
        sta ptr2+1
        ldy #0
@t:     lda (ptr2),y
        beq @next
        jsr emit
        iny
        bne @t
@plain: jsr emit
@next:  inc ptr
        bne @l
        inc ptr+1
        bra @l
@done:  rts

; emit_dec: A = 1..255 in decimal
emit_dec:
        ldx #0
        stz tmp
@h:     cmp #100
        bcc @h2
        sbc #100
        inx
        bra @h
@h2:    cpx #0
        beq @t0
        pha
        txa
        ora #'0'
        jsr emit
        inc tmp
        pla
@t0:    ldx #0
@t:     cmp #10
        bcc @t2
        sbc #10
        inx
        bra @t
@t2:    pha
        txa
        ora tmp
        beq @o
        txa
        ora #'0'
        jsr emit
@o:     pla
        ora #'0'
        jmp emit

; hex: A -> X/Y = two hex digits
hex:    pha
        lsr
        lsr
        lsr
        lsr
        jsr @d
        tax
        pla
        and #$0F
        jsr @d
        tay
        rts
@d:     cmp #10
        bcc @n
        adc #6
@n:     adc #'0'
        rts

; ------------------------------------------------------------------ the conversion
convert:
        php                         ; end of text: aux zero page $1A/$1B
        sei
        sta $C009                   ; ALTZP on (no stack use until it's off)
        lda $1A
        ldx $1B
        sta $C008
        plp
        sta dend
        stx dend+1
        lda WIDTH
        sta width
        beq @ret
        cmp #129
        bcs @ret
        stz src
        lda #$09
        sta src+1
        stz inpara
        stz pend
        stz skip
        stz nextq
        stz on
        stz colour
        stz opened
        stz dirty
        lda #'P'
        sta pstyle
        jmp rowlp
@ret:   rts

rowlp:  lda src
        cmp dend
        lda src+1
        sbc dend+1
        bcc @go
        jmp cfinish
@go:    lda src                     ; AUXMOVE src .. src+width-1 -> ROW
        sta $3C
        clc
        adc width
        sta tmp
        lda src+1
        sta $3D
        adc #0
        sta tmp+1
        lda tmp
        sec
        sbc #1
        sta $3E
        lda tmp+1
        sbc #0
        sta $3F
        lda #<ROW
        sta $42
        lda #>ROW
        sta $43
        clc
        jsr AUXMOVE
        lda tmp
        sta src
        lda tmp+1
        sta src+1

        lda inpara                  ; at a paragraph start: row type
        bne @chk
        lda ROW
        cmp #$1E                    ; custom font command
        bne @n1
        lda #1
        sta skip
@n1:    ldx #'P'
        lda nextq
        beq @n2
        ldx #'Q'
@n2:    lda ROW
        cmp #$1A                    ; footnote row
        bne @n3
        ldx #'F'
@n3:    stx pstyle
@chk:   lda skip
        beq @chars
        ldy #0
@sk:    lda ROW,y
        cmp #$0D
        beq @skend
        iny
        cpy width
        bne @sk
        jmp rowlp
@skend: stz skip
        jmp rowlp
@chars: stz hy
        ldy #0
chlp:   cpy width
        bne @c
        jmp rowend
@c:     lda ROW,y
        cmp #$20
        beq @space
        bcs @print
        cmp #$0D
        beq @cr
        stz hy
        cmp #$0C
        beq @ff
        cmp #$13
        bcc @notcol
        cmp #$19
        bcs @notcol
        cmp colour                  ; colour on/off
        bne @setc
        lda #0
@setc:  sta colour
        lda #1
        sta dirty
        bra chnext
@notcol:
        cmp #$04
        bcc chnext
        cmp #$0C
        bcs chnext
        tax
        lda bitof-4,x
        eor on
        sta on
        lda #1
        sta dirty
        bra chnext
@ff:    lda #1
        sta nextq
        lda inpara
        bne chnext
        lda #'Q'
        sta pstyle
        bra chnext
@space: lda pend
        cmp #$FF
        beq chnext
        inc pend
        bra chnext
@cr:    jsr do_cr
        jmp rowlp
@print: jsr do_print
chnext: iny
        jmp chlp
rowend: lda inpara                  ; soft line wrap
        beq @x
        lda hy
        beq @one
        stz pend
        bra @x
@one:   lda #1
        sta pend
@x:     jmp rowlp

cfinish:
        lda inpara
        beq @x
        jsr close_spans
        lda #<s_pclose
        ldy #>s_pclose
        jsr emit_s
@x:     rts

do_cr:  sty yy
        lda inpara
        bne @close
        jsr p_open_tag
        lda #<s_eclose
        ldy #>s_eclose
        jsr emit_s
        bra @after
@close: jsr close_spans
        lda #<s_pclose
        ldy #>s_pclose
        jsr emit_s
@after: stz inpara
        stz pend
        stz nextq
        lda on
        ora colour
        beq @nd
        lda #1
@nd:    sta dirty
        ldy yy
        rts

do_print:
        sty yy
        sta ntmp                    ; (emit_dec uses tmp)
        stz hy
        cmp #'-'
        bne @h
        cpy #0
        beq @h
        lda ROW-1,y
        cmp #$20
        beq @h
        lda #1
        sta hy
@h:     lda inpara
        bne @ip
        jsr p_open_tag
        lda #'"'
        jsr emit
        lda #'>'
        jsr emit
        lda #1
        sta inpara
@ip:    lda dirty
        beq @nd1
        jsr close_spans
@nd1:   lda pend
        beq @nosp
        cmp #1
        bne @ts
        lda last
        cmp #'>'
        beq @ts
        lda #' '
        jsr emit
        bra @sp0
@ts:    lda #<s_ts
        ldy #>s_ts
        jsr emit_s
        lda pend
        jsr emit_dec
        lda #<s_eclose
        ldy #>s_eclose
        jsr emit_s
@sp0:   stz pend
@nosp:  lda dirty
        beq @nd2
        jsr open_spans
        stz dirty
@nd2:   lda ntmp
        and #$7F
        cmp #'&'
        bne @1
        lda #<s_amp
        ldy #>s_amp
        bra @es
@1:     cmp #'<'
        bne @2
        lda #<s_lt
        ldy #>s_lt
        bra @es
@2:     cmp #'>'
        bne @3
        lda #<s_gt
        ldy #>s_gt
@es:    jsr emit_s
        bra @dn
@3:     jsr emit
@dn:    ldy yy
        rts

p_open_tag:                         ; <text:p text:style-name="X   (no closing quote)
        lda #<s_popen
        ldy #>s_popen
        jsr emit_s
        lda pstyle
        jmp emit

close_spans:
        lda opened
        beq @x
        lda #<s_sclose
        ldy #>s_sclose
        jsr emit_s
        dec opened
        bra close_spans
@x:     rts

open_spans:
        ldx #0
@l:     lda on
        and bitmask,x
        beq @n
        phx
        lda #<s_sopen
        ldy #>s_sopen
        jsr emit_s
        plx
        lda bitname,x
        jsr emit
        jsr s_tagend
        inc opened
@n:     inx
        cpx #8
        bne @l
        lda colour
        beq @x
        lda #<s_sopen
        ldy #>s_sopen
        jsr emit_s
        lda #'C'
        jsr emit
        lda colour
        sec
        sbc #$12
        ora #'0'
        jsr emit
        jsr s_tagend
        inc opened
@x:     rts
s_tagend:
        lda #'"'
        jsr emit
        lda #'>'
        jmp emit

; ------------------------------------------------------------------ messages
okmsg:  ldx #0                      ; msgbuf = ok1 + folder + CR + name + ok2
@a:     lda ok1,x
        beq @fold
        sta msgbuf,x
        inx
        bra @a
@fold:  ldy OUTPATH                 ; find the last '/'
@ls:    lda OUTPATH,y
        cmp #'/'
        beq @sl
        dey
        bne @ls
@sl:    sty tmp                     ; folder = OUTPATH[1..tmp]
        ldy #1
        lda tmp
        cmp #56
        bcc @cp
        lda #'.'                    ; too long: ".." + the last 53 characters
        sta msgbuf,x
        inx
        sta msgbuf,x
        inx
        lda tmp
        sec
        sbc #52
        tay
@cp:    lda OUTPATH,y
        sta msgbuf,x
        inx
        cpy tmp
        beq @nm
        iny
        bra @cp
@nm:    lda #$8D
        sta msgbuf,x
        inx
        lda #' '
        sta msgbuf,x
        inx
@n2:    iny
        lda OUTPATH,y
        sta msgbuf,x
        inx
        cpy OUTPATH
        bne @n2
        ldy #0
@b:     lda ok2,y
        sta msgbuf,x
        inx
        iny
        cpy #ok2len
        bne @b
        rts

; makepath: OUTPATH = document path (at ptr), name cut to 11 characters, + ".ODT".
; C set if that would be too long or would be the document itself.
makepath:
        lda (ptr)               ; ptr = the document's counted pathname
        beq @bad
        cmp #65
        bcs @bad
        tay
@c:     lda (ptr),y
        and #$7F
        sta OUTPATH,y
        dey
        bpl @c
        ldy OUTPATH
@s:     lda OUTPATH,y
        cmp #'/'
        beq @sl
        dey
        bne @s
@sl:    tya                         ; Y = position of the last '/'
        clc
        adc #11
        cmp OUTPATH
        bcs @fit
        sta OUTPATH                 ; cut the name to 11 characters
        tay
        lda OUTPATH,y               ; and drop a '.' left at the end
        cmp #'.'
        bne @fit
        dec OUTPATH
@fit:   lda OUTPATH
        cmp #61
        bcs @bad
        tay
        ldx #0
@e:     lda s_odt,x
        iny
        sta OUTPATH,y
        inx
        cpx #4
        bne @e
        sty OUTPATH
        tya                         ; same as the document's own name?
        cmp (ptr)
        bne @ok
@cmp:   lda OUTPATH,y
        eor (ptr),y
        and #$7F
        cmp #0
        beq @eq
        cmp #$20                    ; letter case only
        bne @ok
@eq:    dey
        bne @cmp
@bad:   sec
        rts
@ok:    clc
        rts

; ------------------------------------------------------------------ data
bitof:  .byte $02,$01,$40,$80,$10,$20,$04,$08   ; style codes $04-$0B -> bit
bitmask:.byte $01,$02,$04,$08,$10,$20,$40,$80
bitname:.byte "BUIKSDNW"
s_odt:  .byte ".ODT"
s_popen:.byte "<text:p text:style-name=", '"', 0
s_eclose:.byte '"', "/>", 0
s_pclose:.byte "</text:p>", 0
s_sopen:.byte "<text:span text:style-name=", '"', 0
s_sclose:.byte "</text:span>", 0
s_ts:   .byte "<text:s text:c=", '"', 0
s_amp:  .byte "&amp;", 0
s_lt:   .byte "&lt;", 0
s_gt:   .byte "&gt;", 0

msg_nodoc:
        .byte " Please open a document first.", $8D, 0
        .byte 1, "OK ", $0D, 0, 3
msg_untitled:
        .byte " Please save this document first.", $8D, $8D
        .byte " The .ODT file is saved next to it, with", $8D
        .byte " the same name.", $8D, 0
        .byte 1, "OK ", $0D, 0, 3
msg_name:
        .byte " The .ODT file would replace this document.", $8D, $8D
        .byte " Please save it under another name first.", $8D, 0
        .byte 1, "OK ", $0D, 0, 3
msg_err:
        .byte " The .ODT file could not be saved.", $8D, $8D
        .byte " ProDOS error $"
msg_err_hex:
        .byte "00", $8D, 0
        .byte 1, "OK ", $0D, 0, 3
ok1:    .byte " Saved for LibreOffice and OpenOffice as:", $8D, $8D, " ", 0
ok2:    .byte $8D, 0, 1, "OK ", $0D, 0, 3
ok2len = * - ok2

p_destroy:
        .byte 1
        .word OUTPATH
p_create:
        .byte 7
        .word OUTPATH
        .byte $C3, $06          ; access, file type BIN
        .word 0                 ; aux type
        .byte 1                 ; seedling
        .word 0, 0              ; date/time: now
p_open: .byte 3
        .word OUTPATH
        .word IOBUF
        .byte 0
p_write:.byte 4, 0
        .word 0, 0, 0
p_mark: .byte 2, 0, 0, 0, 0
p_close:.byte 1, 0

        .include "mwod.inc"

msgbuf: .res 140                ; the "Saved ... as" message

        .assert * <= LANDING, error, "MW.OD is too big for the overlay window"
        .res LANDING - *, 0
        jmp export              ; o6patch's JSR LOADOVL returns here
        jsr LOADOVL             ; RELOAD: reload MW.O6; returns to o6patch's RTS
        .assert * = RELOAD + 3, error, "fixed entries"

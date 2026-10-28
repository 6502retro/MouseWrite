; MWFIX - self-locating add-on for MouseWrite 2.6.8b MW.SYSTEM
;
; Appended to the end of MW.SYSTEM (which loads at $2000-$3E18) and entered
; from MW.SYSTEM's own JMP at $2000 (retargeted from $2046 to here).
;
; MouseWrite keeps three absolute pathnames in its preference files:
;   MW.GP  $00-$3D  Standard Document Location   (length byte at $3E)
;   MW.GP  $40-$7D  Standard Desk Accessory Loc. (length byte at $3F)
;   MW.UI  $3B-$78  Standard Speller Location    (length byte at $3A)
; As shipped they point at /MOUSEWRITE/SAMPLES/, /MOUSEWRITE/ACCESSORY/ and
; /MOUSEWRITE/SPELLER/, which do not exist once MouseWrite lives in a folder
; on a hard disk.  Before MouseWrite starts, this code checks each one.  If the
; folder it names can't be found, AND a folder of the expected name exists next
; to MW.SYSTEM (in the current ProDOS prefix), the path is rewritten to that
; folder and the preference file is updated on disk.  Paths that work are never
; touched, so choices made in Startup Preferences are kept.
; Then it continues into MouseWrite exactly as before (JMP $2046).

MLI     = $BF00
IOBUF   = $1C00         ; 1K ProDOS I/O buffer
BUF     = $1B00         ; first 128 bytes of a preference file
TEMP    = $6000         ; splash: aux half is staged here

        .org $1000
start:  jsr MLI         ; GET_PREFIX
        .byte $C7
        .word gp_parms
        bcs done
        lda pfx
        beq done        ; no prefix set: nothing we can do

        ; ---- MW.GP: document and accessory locations
        lda #<name_gp
        ldx #>name_gp
        jsr openread
        bcs @ui
        lda #$3E        ; length offset
        ldx #$00        ; string offset
        ldy #0          ; sub-folder 0 = SAMPLES/
        jsr fixentry
        lda #$3F
        ldx #$40
        ldy #1          ; ACCESSORY/
        jsr fixentry
        jsr writeclose

        ; ---- MW.UI: speller location
@ui:    lda #<name_ui
        ldx #>name_ui
        jsr openread
        bcs done
        lda #$3A
        ldx #$3B
        ldy #2          ; SPELLER/
        jsr fixentry
        jsr writeclose

done:   jmp splash

; ---------------------------------------------------------------------------
; splash: show MW.SPLASH (double hi-res, 8K aux + 8K main) for ~3 seconds or
; until a key is pressed, then start MouseWrite.  Skipped when MouseWrite is
; restarting itself (e.g. after BYE from the Basic.System accessory), which it
; marks with "MW" + checksum at $0800 - the same test MW.SYSTEM makes.
splash:
        lda $0800
        cmp #'M'
        bne @show
        lda $0801
        cmp #'W'
        bne @show
        eor $0800
        cmp $0802
        bne @show
@go0:   jmp $2046       ; restarting: no splash
@show:  lda #<name_sp
        sta op_path
        lda #>name_sp
        sta op_path+1
        jsr MLI
        .byte $C8       ; OPEN
        .word op_parms
        bcs @go0
        lda op_ref
        sta rs_ref
        sta cl_ref
        lda #<TEMP      ; aux half -> main $6000 first
        sta rs_buf
        lda #>TEMP
        sta rs_buf+1
        jsr readhalf
        bcs @close
        sta $C005       ; RAMWRT: writes go to aux memory
        lda #<TEMP
        sta $06
        lda #>TEMP
        sta $07
        lda #$00
        sta $08
        lda #$40
        sta $09
        ldx #$20
        ldy #0
@cp:    lda ($06),y
        sta ($08),y
        iny
        bne @cp
        inc $07
        inc $09
        dex
        bne @cp
        sta $C004       ; RAMWRT off
        lda #$00        ; main half -> $4000 (hi-res page 2)
        sta rs_buf
        lda #$40
        sta rs_buf+1
        jsr readhalf
        php
        jsr MLI
        .byte $CC       ; CLOSE
        .word cl_parms
        plp
        bcs @go
        ; double hi-res, page 2
        sta $C000       ; 80STORE off
        sta $C00D       ; 80 columns on
        lda $C050       ; graphics
        lda $C052       ; full screen
        lda $C057       ; hi-res
        lda $C055       ; page 2
        lda $C05E       ; double hi-res on
        bit $C010
        lda #9          ; ~3 seconds at 1 MHz
        sta $0A
@o:     ldy #0
@m:     ldx #0
@i:     dex
        bne @i
        lda $C000
        bmi @key
        dey
        bne @m
        dec $0A
        bne @o
        beq @off
@key:   bit $C010
@off:   lda $C05F       ; double hi-res off
        lda $C054       ; page 1
        lda $C051       ; text
        jmp @go
@close: jsr MLI
        .byte $CC
        .word cl_parms
@go:    jmp $2046       ; MW.SYSTEM's original entry point

readhalf:               ; read 8K; C set unless all 8K arrived
        jsr MLI
        .byte $CA       ; READ
        .word rs_parms
        bcs @bad
        lda rs_trans
        bne @bad
        lda rs_trans+1
        cmp #$20
        bne @bad
        clc
        rts
@bad:   sec
        rts

; ---------------------------------------------------------------------------
; openread: A/X = pathname.  Opens the file and reads up to 128 bytes to BUF.
; Returns C set on failure (file left closed).
openread:
        sta op_path
        stx op_path+1
        lda #0
        sta dirty
        jsr MLI
        .byte $C8       ; OPEN
        .word op_parms
        bcs @fail
        lda op_ref
        sta rd_ref
        sta sm_ref
        sta wr_ref
        sta cl_ref
        jsr MLI
        .byte $CA       ; READ
        .word rd_parms
        bcs @closefail
        lda rd_trans+1  ; need the whole 128 bytes
        bne @ok
        lda rd_trans
        cmp #$80
        bcc @closefail
@ok:    clc
        rts
@closefail:
        jsr MLI
        .byte $CC       ; CLOSE
        .word cl_parms
@fail:  sec
        rts

; writeclose: if anything changed, rewrite the 128 bytes at mark 0; close.
writeclose:
        lda dirty
        beq @close
        jsr MLI
        .byte $CE       ; SET_MARK 0
        .word sm_parms
        bcs @close
        jsr MLI
        .byte $CB       ; WRITE
        .word wr_parms
@close: jsr MLI
        .byte $CC       ; CLOSE
        .word cl_parms
        rts

; ---------------------------------------------------------------------------
; fixentry: A = offset of length byte in BUF, X = offset of string in BUF,
;           Y = sub-folder index (0..2).  Field is 62 bytes long.
fixentry:
        sta lenoff
        stx stroff
        lda subtab_lo,y
        sta subptr
        lda subtab_hi,y
        sta subptr+1
        lda filltab,y
        sta fill2

        ; --- copy current path to tpath, without a trailing '/'
        ldy lenoff
        lda BUF,y
        beq @sk0        ; empty = feature turned off; leave alone
        cmp #63
        bcc @lenok      ; else not a sane length
@sk0:   rts
@lenok: sta curlen
        ldx stroff
        ldy #0
@cp:    lda BUF,x
        sta tpath+1,y
        inx
        iny
        cpy curlen
        bne @cp
        lda tpath,y     ; last char copied (tpath+1+y-1)
        cmp #'/'
        bne @nos
        dey
@nos:   sty tpath
        cpy #0
        beq @skip
        jsr getinfo
        bcc @skip       ; path works: keep the user's setting

        ; --- build prefix + sub-folder in tpath
        ldx #0
@pf:    lda pfx+1,x
        sta tpath+1,x
        inx
        cpx pfx
        bne @pf
        jsr subcopy     ; appends sub-folder name, X = new length
        cpx #62
        bcs @skip       ; would not fit in MouseWrite's field
        stx newlen
        dex             ; drop trailing '/' for the existence test
        stx tpath
        jsr getinfo
        bcs @skip       ; no such folder next to MW.SYSTEM: leave alone

        ; --- store new path into BUF
        ldx stroff
        ldy #0
@st:    lda tpath+1,y
        sta BUF,x
        inx
        iny
        cpy newlen
        bne @st
        ; tpath lacks the final '/', but newlen includes it
        dex
        lda #'/'
        sta BUF,x
        inx
        lda #' '
        sta BUF,x
        inx
        iny
        ; pad rest of the 62-byte field
@pad:   cpy #62
        bcs @len
        lda fill2
        sta BUF,x
        inx
        iny
        bne @pad
@len:   ldy lenoff
        lda newlen
        sta BUF,y
        lda #1
        sta dirty
@skip:  rts

; subcopy: append sub-folder string (Pascal string at subptr) to tpath,
; starting at index X (count so far).  Returns X = total length.
subcopy:
        lda subptr
        sta @rd+1
        sta @ln+1
        lda subptr+1
        sta @rd+2
        sta @ln+2
@ln:    lda $FFFF       ; length of sub-folder string
        sta sublen
        ldy #1
@rd:    lda $FFFF,y
        sta tpath+1,x
        inx
        cpy sublen
        iny
        bcc @rd
        rts

getinfo:
        jsr MLI
        .byte $C4       ; GET_FILE_INFO
        .word gi_parms
        rts

; ---------------------------------------------------------------------------
subtab_lo: .byte <sub0, <sub1, <sub2
subtab_hi: .byte >sub0, >sub1, >sub2
filltab:   .byte $00, $00, $20      ; MW.GP fields are 0-filled, MW.UI space-filled
sub0:   .byte 8, "SAMPLES/"
sub1:   .byte 10, "ACCESSORY/"
sub2:   .byte 8, "SPELLER/"
name_gp: .byte 5, "MW.GP"
name_ui: .byte 5, "MW.UI"
name_sp: .byte 9, "MW.SPLASH"

gp_parms: .byte 1
        .word pfx
op_parms: .byte 3
op_path: .word 0
        .word IOBUF
op_ref: .byte 0
rd_parms: .byte 4
rd_ref: .byte 0
        .word BUF
        .word 128
rd_trans: .word 0
sm_parms: .byte 2
sm_ref: .byte 0
        .byte 0,0,0
wr_parms: .byte 4
wr_ref: .byte 0
        .word BUF
        .word 128
        .word 0
rs_parms: .byte 4
rs_ref: .byte 0
rs_buf: .word 0
        .word $2000
rs_trans: .word 0
cl_parms: .byte 1
cl_ref: .byte 0
gi_parms: .byte $0A
        .word tpath
        .res 15

dirty:  .byte 0
lenoff: .byte 0
stroff: .byte 0
curlen: .byte 0
newlen: .byte 0
fill2:  .byte 0
subptr: .word 0
sublen: .byte 0
pfx:    .res 65
tpath:  .res 130

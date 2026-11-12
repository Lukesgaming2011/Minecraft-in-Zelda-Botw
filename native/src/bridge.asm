[HyruleBlocks_V208]
moduleMatches = {{MODULE}}
.origin = codecave
.align 8
HBMailbox:
{{MAILBOX_DATA}}
.align 4
{{PLAYER_SINGLETON}} = HBPlayerInfo:

; Capture the game's normal map-actor creation context before its original prologue.
HBCaptureCreate:
stwu r1, -0x20(r1)
stw r0, 0x04(r1)
stw r11, 0x08(r1)
stw r12, 0x0C(r1)
.int 0x7C000026 ; mfcr r0
stw r0, 0x10(r1)
mfctr r0
stw r0, 0x14(r1)
lis r11, HBMailbox@ha
addi r11, r11, HBMailbox@l
lwz r0, 0x190(r11)
cmpwi r0, 0
bne HBCaptureDone
cmpwi r7, 0
beq HBCaptureDone
stw r3, 0x28(r11)
stw r5, 0x2C(r11)
; Copy 104 bytes using integer operations; do not clobber floating registers.
li r12, 0
HBCopyArgs:
lwzx r0, r7, r12
add r11, r11, r12
stw r0, 0x70(r11)
subf r11, r12, r11
addi r12, r12, 4
cmpwi r12, 104
blt HBCopyArgs
li r0, 1
stw r0, 0x1C(r11)
HBCaptureDone:
lwz r0, 0x14(r1)
mtctr r0
lwz r0, 0x10(r1)
.int 0x7C0FF120 ; mtcrf 255, r0
lwz r12, 0x0C(r1)
lwz r11, 0x08(r1)
lwz r0, 0x04(r1)
addi r1, r1, 0x20
stwu r1, -0x38(r1)
b 0x037b6044
{{CREATE}} = b HBCaptureCreate

; Observe completed insertion, recording only the requested actor name.
HBNewActor:
stw r7, 0x20(r28)
stwu r1, -0x30(r1)
stw r0, 0x04(r1)
stw r8, 0x08(r1)
stw r9, 0x0C(r1)
stw r10, 0x10(r1)
stw r11, 0x14(r1)
stw r12, 0x18(r1)
.int 0x7C000026 ; mfcr r0
stw r0, 0x1C(r1)
lis r11, HBMailbox@ha
addi r11, r11, HBMailbox@l
lwz r0, 0x190(r11)
cmpwi r0, 0
beq HBNewDone
lwz r8, 0x04(r30)
cmpwi r8, 0
beq HBNewDone
li r12, 0
HBNameCompare:
lbzx r9, r8, r12
add r10, r11, r12
lbz r10, 0x150(r10)
cmpw r9, r10
bne HBNewDone
cmpwi r9, 0
beq HBNameMatched
addi r12, r12, 1
cmpwi r12, 63
blt HBNameCompare
b HBNewDone
HBNameMatched:
stw r30, 0x24(r11)
li r0, 0
stw r0, 0x190(r11)
li r0, 2
stw r0, 0x14(r11)
HBNewDone:
lwz r0, 0x1C(r1)
.int 0x7C0FF120 ; mtcrf 255, r0
lwz r12, 0x18(r1)
lwz r11, 0x14(r1)
lwz r10, 0x10(r1)
lwz r9, 0x0C(r1)
lwz r8, 0x08(r1)
lwz r0, 0x04(r1)
addi r1, r1, 0x30
b 0x037b769c
{{NEW_ACTOR}} = b HBNewActor

HBCamera:
mr r3, r31
stwu r1, -0x10(r1)
stw r11, 0x04(r1)
lis r11, HBMailbox@ha
addi r11, r11, HBMailbox@l
stw r3, 0x1B0(r11)
lwz r11, 0x04(r1)
addi r1, r1, 0x10
b 0x02b966a8
{{CAMERA}} = b HBCamera

; Verified final ActCamera update sites: each branch finishes its native
; position/target before culling and LookAt matrix generation. Reflect only
; the presentation camera for Minecraft's front view; native orbit stays intact.
HBFinalCameraA:
stfs f0, 0x5CC(r31)
stwu r1, -0x10(r1)
stw r0, 4(r1)
mflr r0
stw r0, 0x14(r1)
bl HBFrontCamera
lwz r0, 0x14(r1)
mtlr r0
lwz r0, 4(r1)
addi r1, r1, 0x10
b 0x02c05500
{{CAMERA_FINAL_A}} = b HBFinalCameraA
HBFinalCameraB:
stfs f13, 0x5C4(r31)
stwu r1, -0x10(r1)
stw r0, 4(r1)
mflr r0
stw r0, 0x14(r1)
bl HBFrontCamera
lwz r0, 0x14(r1)
mtlr r0
lwz r0, 4(r1)
addi r1, r1, 0x10
b 0x02c05594
{{CAMERA_FINAL_B}} = b HBFinalCameraB
HBHalf:
.float 0.5
HBThreeHalves:
.float 1.5
HBMinLengthSquared:
.float 0.000001
HBMinCameraDistance:
.float 0.05
HBMaxCameraDistance:
.float 6.1
HBFrontCamera:
stwu r1, -0x70(r1)
stw r11, 72(r1)
stw r12, 76(r1)
stw r0, 4(r1)
stw r9, 8(r1)
stw r10, 12(r1)
.int 0x7C000026 ; mfcr r0
stw r0, 16(r1)
stfd f0, 24(r1)
stfd f1, 32(r1)
stfd f2, 40(r1)
stfd f3, 48(r1)
stfd f4, 56(r1)
stfd f5, 64(r1)
lis r9, HBMailbox@ha
addi r9, r9, HBMailbox@l
lwz r10, 0x1EC(r9)
addi r10, r10, 1
stw r10, 0x1EC(r9) ; publish odd while orientation/ack are changing
.int 0x7C0004AC ; sync
lwz r10, 0x1CC(r9)
addi r10, r10, 1
stw r10, 0x1CC(r9)
li r0, 0
stw r0, 0x1D0(r9)
; Capture unmodified gameplay aim in the same generation as the camera ack.
lfs f0, 0x5CC(r31)
lfs f3, 0x5C0(r31)
fsubs f0, f0, f3
stfs f0, 0x1D4(r9)
lfs f1, 0x5D0(r31)
lfs f3, 0x5C4(r31)
fsubs f1, f1, f3
stfs f1, 0x1D8(r9)
lfs f2, 0x5D4(r31)
lfs f3, 0x5C8(r31)
fsubs f2, f2, f3
stfs f2, 0x1DC(r9)
; Host-owned direct mouse aim: unit vector, seqlock, short camera-frame lease.
lwz r0, 0x40(r9)
andi. r0, r0, 1
beq HBMouseAimDone
lwz r11, 0x44(r9)
andi. r0, r11, 1
bne HBMouseAimDone
lwz r0, 0x68(r9)
subf r0, r0, r10
cmplwi r0, 15
bgt HBMouseAimDone
lfs f0, 0x5C(r9)
lfs f1, 0x60(r9)
lfs f2, 0x64(r9)
.int 0x7C0004AC
lwz r0, 0x44(r9)
cmpw r0, r11
bne HBMouseAimRestore
fmuls f3, f0, f0
fmadds f3, f1, f1, f3
fmadds f3, f2, f2, f3
fcmpu cr0, f3, f3
bne HBMouseAimRestore
lis r11, HBMouseUnitMin@ha
lfs f4, HBMouseUnitMin@l(r11)
fcmpu cr0, f3, f4
blt HBMouseAimRestore
lis r11, HBMouseUnitMax@ha
lfs f4, HBMouseUnitMax@l(r11)
fcmpu cr0, f3, f4
bgt HBMouseAimRestore
stfs f0, 0x1D4(r9)
stfs f1, 0x1D8(r9)
stfs f2, 0x1DC(r9)
lwz r0, 0x1C4(r9)
cmpwi r0, 0
bne HBMouseAimDone
; First person: keep native eye and set an exact target three metres ahead.
lis r11, HBMouseAimLength@ha
lfs f3, HBMouseAimLength@l(r11)
fmuls f4, f0, f3
lfs f5, 0x5C0(r31)
fadds f4, f4, f5
stfs f4, 0x5CC(r31)
fmuls f4, f1, f3
lfs f5, 0x5C4(r31)
fadds f4, f4, f5
stfs f4, 0x5D0(r31)
fmuls f4, f2, f3
lfs f5, 0x5C8(r31)
fadds f4, f4, f5
stfs f4, 0x5D4(r31)
b HBFrontCameraDone
HBMouseAimRestore:
lfs f0, 0x1D4(r9)
lfs f1, 0x1D8(r9)
lfs f2, 0x1DC(r9)
HBMouseAimDone:
lwz r0, 0x1C4(r9)
cmpwi r0, 1
beq HBCameraLease
cmpwi r0, 2
bne HBFrontCameraDone
HBCameraLease:
lwz r0, 0x1C8(r9)
subf r0, r0, r10
cmplwi r0, 15
bgt HBFrontCameraDone
; Normalize native orbit; one Newton refinement of frsqrte. First-person
; distance remains native; detached cameras use MC's collision-clipped zoom.
fmuls f3, f0, f0
fmadds f3, f1, f1, f3
fmadds f3, f2, f2, f3
lis r10, HBMinLengthSquared@ha
lfs f4, HBMinLengthSquared@l(r10)
fcmpu cr0, f3, f4
bgt HBCameraLengthValid
b HBFrontCameraDone
HBCameraLengthValid:
fmr f4, f3
frsqrte f3, f3
fmul f5, f3, f3
fmul f5, f4, f5
lis r10, HBHalf@ha
lfs f4, HBHalf@l(r10)
fmul f5, f4, f5
lis r10, HBThreeHalves@ha
lfs f4, HBThreeHalves@l(r10)
fsub f4, f4, f5
fmul f3, f3, f4
lfs f4, 0x1F0(r9)
lis r10, HBMinCameraDistance@ha
lfs f5, HBMinCameraDistance@l(r10)
fcmpu cr0, f4, f5
bgt HBCameraMinValid
b HBFrontCameraDone
HBCameraMinValid:
lis r10, HBMaxCameraDistance@ha
lfs f5, HBMaxCameraDistance@l(r10)
fcmpu cr0, f4, f5
blt HBCameraDistanceValid
b HBFrontCameraDone
HBCameraDistanceValid:
fmul f3, f3, f4
lwz r0, 0x1C4(r9)
cmpwi r0, 2
bne HBCameraScaleReady
fneg f3, f3
HBCameraScaleReady:
fmuls f0, f0, f3
fmuls f1, f1, f3
fmuls f2, f2, f3
lfs f4, 0x5CC(r31)
fsubs f0, f4, f0
stfs f0, 0x5C0(r31)
lfs f4, 0x5D0(r31)
fsubs f1, f4, f1
stfs f1, 0x5C4(r31)
lfs f4, 0x5D4(r31)
fsubs f2, f4, f2
stfs f2, 0x5C8(r31)
stw r0, 0x1D0(r9)
HBFrontCameraDone:
lwz r10, 0x1EC(r9)
addi r10, r10, 1
.int 0x7C0004AC ; sync
stw r10, 0x1EC(r9) ; orientation and acknowledgement are now one generation
lfd f0, 24(r1)
lfd f1, 32(r1)
lfd f2, 40(r1)
lfd f3, 48(r1)
lfd f4, 56(r1)
lfd f5, 64(r1)
lwz r0, 16(r1)
.int 0x7C0FF120 ; mtcrf 255,r0
lwz r10, 12(r1)
lwz r9, 8(r1)
lwz r0, 4(r1)
lwz r11, 72(r1)
lwz r12, 76(r1)
addi r1, r1, 0x70
blr

HBMouseUnitMin:
.float 0.99
HBMouseUnitMax:
.float 1.01
HBMouseAimLength:
.float 3.0
HBSupportMaxSquared:
.float 0.5625

; v208 camera distance: reproduce original loads, then select zero distance.
HBFirstPersonZero:
.float 0.0
HBFirstPersonDistance:
lis r9, 0x1021
lis r12, 0x1021
lfs f13, 0x6594(r9)
lfs f12, 0x6598(r12)
stwu r1, -0x10(r1)
stw r0, 4(r1)
.int 0x7C000026 ; mfcr r0
stw r0, 8(r1)
lis r9, HBMailbox@ha
addi r9, r9, HBMailbox@l
lwz r0, 0x1B4(r9)
cmpwi r0, 0
beq HBFirstPersonDone
lis r9, HBFirstPersonZero@ha
lfs f13, HBFirstPersonZero@l(r9)
HBFirstPersonDone:
lwz r0, 8(r1)
.int 0x7C0FF120 ; mtcrf 255, r0
lwz r0, 4(r1)
addi r1, r1, 0x10
lis r9, 0x1021
b 0x02e5fec8
{{CAMERA_DISTANCE}} = b HBFirstPersonDistance
0x02e5febc = nop
0x02e5fec0 = nop
0x02e5fec4 = nop

; Consume one request on the game's execution path, preserving all volatile state.
HBTick:
stwu r1, -0x110(r1)
stw r0, 0x08(r1)
.int 0xBC61000C ; stmw r3, 0x0C(r1)
mflr r0
stw r0, 0x84(r1)
mfctr r0
stw r0, 0x88(r1)
.int 0x7C000026 ; mfcr r0
stw r0, 0x8C(r1)
stfd f0, 0x90(r1)
stfd f1, 0x98(r1)
stfd f2, 0xA0(r1)
stfd f3, 0xA8(r1)
stfd f4, 0xB0(r1)
stfd f5, 0xB8(r1)
stfd f6, 0xC0(r1)
stfd f7, 0xC8(r1)
stfd f8, 0xD0(r1)
stfd f9, 0xD8(r1)
stfd f10, 0xE0(r1)
stfd f11, 0xE8(r1)
stfd f12, 0xF0(r1)
stfd f13, 0xF8(r1)
lis r31, HBMailbox@ha
addi r31, r31, HBMailbox@l
lwz r3, 0x18(r31)
addi r3, r3, 1
stw r3, 0x18(r31)
lis r3, HBPlayerInfo@ha
lwz r3, HBPlayerInfo@l(r3)
cmpwi r3, 0
beq HBNoPlayer
lwz r3, 0x30(r3)
HBNoPlayer:
stw r3, 0x20(r31)
; Only actor-update calls may dispatch placement. VPAD calls update telemetry.
lwz r3, 0x0C(r1)
lis r0, 0x1000
cmpw r3, r0
blt HBTickDone
addi r12, r31, 0x10
.int 0x7C606028 ; lwarx r3, 0, r12
cmpwi r3, 0
beq HBTickDone
cmpwi r3, 3
beq HBTickDone ; Link movement belongs to the dedicated player tick.
cmpwi r3, 4
beq HBTickDone ; Explicit home recovery also belongs to the player tick.
li r0, 0
.int 0x7C00612D ; stwcx. r0, 0, r12: claim request once across actor threads
bne HBTickDone
cmpwi r3, 1
beq HBPlace
cmpwi r3, 2
beq HBRemove
b HBTickDone
HBPlace:
li r0, 0
stw r0, 0x10(r31)
lwz r0, 0x1C(r31)
cmpwi r0, 1
bne HBRequestInvalid
lwz r3, 0x20(r31)
cmpwi r3, 0
beq HBRequestInvalid
lwz r0, 0x190(r31)
cmpwi r0, 0
bne HBRequestInvalid
li r0, 1
stw r0, 0x190(r31)
stw r0, 0x14(r31)
li r0, 0
stw r0, 0x24(r31)
lwz r3, 0x28(r31)
addi r4, r31, 0x150
lwz r5, 0x2C(r31)
addi r6, r31, 0xFC
addi r7, r31, 0xE0
li r8, 0
li r9, 1
li r10, 0
bl {{CREATE}}
stw r3, 0x1A8(r31)
cmpwi r3, 0
bne HBTickDone
li r0, 0
stw r0, 0x190(r31)
li r0, -1
stw r0, 0x14(r31)
b HBTickDone
HBRemove:
li r0, 0
stw r0, 0x10(r31)
lwz r3, 0x34(r31)
cmpwi r3, 0
beq HBRequestInvalid
li r4, 0
bl {{DELETE}}
stw r3, 0x14(r31)
b HBTickDone
HBRequestInvalid:
li r0, -1
stw r0, 0x14(r31)
HBTickDone:
lfd f13, 0xF8(r1)
lfd f12, 0xF0(r1)
lfd f11, 0xE8(r1)
lfd f10, 0xE0(r1)
lfd f9, 0xD8(r1)
lfd f8, 0xD0(r1)
lfd f7, 0xC8(r1)
lfd f6, 0xC0(r1)
lfd f5, 0xB8(r1)
lfd f4, 0xB0(r1)
lfd f3, 0xA8(r1)
lfd f2, 0xA0(r1)
lfd f1, 0x98(r1)
lfd f0, 0x90(r1)
lwz r0, 0x8C(r1)
.int 0x7C0FF120 ; mtcrf 255, r0
lwz r0, 0x88(r1)
mtctr r0
lwz r0, 0x84(r1)
mtlr r0
.int 0xB861000C ; lmw r3, 0x0C(r1)
lwz r0, 0x08(r1)
addi r1, r1, 0x110
blr

; Execute requests from the actor job thread before the verified original prologue.
HBActorTick:
stwu r1, -0x20(r1)
mflr r0
stw r0, 0x24(r1)
bl HBTick
lwz r0, 0x24(r1)
mtlr r0
addi r1, r1, 0x20
stwu r1, -0xB0(r1)
b 0x024adacc
{{ACTOR_UPDATE}} = b HBActorTick

; Player-only execution point. Preserve the interrupted function's state.
; Command 3 moves through Link's verified virtual setMtx, never raw actor writes.
; Verified live Link vtable+0x2A4 resolves to PLAYER_TICK itself:
; this is updateMtxFromPhysics. Correct AFTER it republishes native physics.
HBPlayerTick:
stwu r1, -0x20(r1)
mflr r0
stw r0, 0x24(r1)
stw r3, 0x08(r1)
bl HBOriginalPlayerSync
stw r3, 0x0C(r1)
lwz r3, 0x08(r1)
bl HBPlayerCorrection
lwz r3, 0x0C(r1)
lwz r0, 0x24(r1)
mtlr r0
addi r1, r1, 0x20
blr
HBOriginalPlayerSync:
mflr r0
b 0x02d67cf8
HBPlayerCorrection:
stwu r1, -0x160(r1)
stw r0, 0x08(r1)
.int 0xBC61000C ; stmw r3, 0x0C(r1)
mflr r0
stw r0, 0x84(r1)
mfctr r0
stw r0, 0x88(r1)
.int 0x7C000026
stw r0, 0x8C(r1)
stfd f0, 0x90(r1)
stfd f1, 0x98(r1)
stfd f2, 0xA0(r1)
stfd f3, 0xA8(r1)
stfd f4, 0xB0(r1)
stfd f5, 0xB8(r1)
stfd f6, 0xC0(r1)
stfd f7, 0xC8(r1)
stfd f8, 0xD0(r1)
stfd f9, 0xD8(r1)
stfd f10, 0xE0(r1)
stfd f11, 0xE8(r1)
stfd f12, 0xF0(r1)
stfd f13, 0xF8(r1)
lis r31, HBMailbox@ha
addi r31, r31, HBMailbox@l
lwz r0, 0x20(r31)
cmpw r3, r0
bne HBPlayerDone
; Known USv208 Link vtable, before touching researched render-only fields.
lwz r12, 0xE8(r3)
lis r0, 0x101E
ori r0, r0, 0x5FFC
cmpw r12, r0
bne HBPlayerDone
; Restore Link automatically when a fresh exported MC avatar is unavailable.
; 33C=modelOpacity and436=opacity GPU dirty byte, BetterVR camera.cpp.
lwz r0, 0x1F4(r31)
cmpwi r0, 1
bne HBRestoreModel
lwz r0, 0x1C4(r31)
cmpwi r0, 1
beq HBModelLease
cmpwi r0, 2
bne HBRestoreModel
HBModelLease:
lwz r0, 0x1C8(r31)
lwz r12, 0x1CC(r31)
subf r0, r0, r12
cmplwi r0, 15
bgt HBRestoreModel
lwz r0, 0x1FC(r31)
cmpw r0, r3
beq HBHideModel
; Only store a bounded original opacity once for this actor identity.
lfs f0, 0x33C(r3)
fcmpu cr0, f0, f0
beq HBModelOpacityFinite
b HBModelDone
HBModelOpacityFinite:
lis r12, HBFirstPersonZero@ha
lfs f1, HBFirstPersonZero@l(r12)
fcmpu cr0, f0, f1
bge HBModelNonnegative
b HBModelDone
HBModelNonnegative:
lis r12, HBThreeHalves@ha
lfs f1, HBThreeHalves@l(r12)
fcmpu cr0, f0, f1
ble HBModelOpacityValid
b HBModelDone
HBModelOpacityValid:
stfs f0, 0x1F8(r31)
stw r3, 0x1FC(r31)
HBHideModel:
li r0, 0
stw r0, 0x33C(r3)
li r0, 1
stb r0, 0x436(r3)
b HBModelDone
HBRestoreModel:
lwz r0, 0x1FC(r31)
cmpw r0, r3
bne HBModelDone
lwz r0, 0x1F8(r31)
stw r0, 0x33C(r3)
li r0, 1
stb r0, 0x436(r3)
li r0, 0
stw r0, 0x1FC(r31)
HBModelDone:
addi r12, r31, 0x10
.int 0x7C006028 ; lwarx r0, 0, r12
cmpwi r0, 3
beq HBPlayerClaimNudge
cmpwi r0, 4
bne HBPlayerHold
li r7, 2
b HBPlayerClaim
HBPlayerClaimNudge:
li r7, 0
HBPlayerClaim:
li r0, 0
.int 0x7C00612D
bne HBPlayerDone
b HBPlayerMatrixGate
HBPlayerHold:
; Reapply only the last bounded, verified correction while the host is fresh.
lwz r0, 0x40(r31)
andi. r0, r0, 2
beq HBPlayerDone
lwz r0, 0x68(r31)
lwz r12, 0x1CC(r31)
subf r0, r0, r12
cmplwi r0, 4
bgt HBPlayerDone
lwz r0, 0x214(r31)
cmpw r0, r3
bne HBPlayerDone
lfs f0, 0x204(r3)
lfs f1, 0x208(r31)
fsubs f0, f0, f1
fmuls f3, f0, f0
lfs f0, 0x214(r3)
lfs f1, 0x20C(r31)
fsubs f0, f0, f1
fmadds f3, f0, f0, f3
lfs f0, 0x224(r3)
lfs f1, 0x210(r31)
fsubs f0, f0, f1
fmadds f3, f0, f0, f3
fcmpu cr0, f3, f3
bne HBPlayerDone
lis r12, HBSupportMaxSquared@ha
lfs f4, HBSupportMaxSquared@l(r12)
fcmpu cr0, f3, f4
bgt HBPlayerDone
li r7, 1
HBPlayerMatrixGate:
stw r7, 0x144(r1)
lwz r12, 0xE8(r3)
lis r0, 0x101E
ori r0, r0, 0x5FFC
cmpw r12, r0
bne HBPlayerInvalid
lwz r12, 0x2AC(r12)
lis r0, 0x02D6
ori r0, r0, 0x6ABC
cmpw r12, r0
bne HBPlayerInvalid
mtctr r12
li r9, 0
HBPlayerCopyMatrix:
addi r8, r3, 0x1F8
lwzx r0, r8, r9
addi r8, r1, 0x110
stwx r0, r8, r9
addi r9, r9, 4
cmpwi r9, 48
blt HBPlayerCopyMatrix
cmpwi r7, 1
beq HBPlayerUseHold
addi r8, r31, 0x1B8
b HBPlayerTargetReady
HBPlayerUseHold:
addi r8, r31, 0x208
HBPlayerTargetReady:
lwz r0, 0(r8)
stw r0, 0x11C(r1)
stw r0, 0x208(r31)
lwz r0, 4(r8)
stw r0, 0x12C(r1)
stw r0, 0x20C(r31)
lwz r0, 8(r8)
stw r0, 0x13C(r1)
stw r0, 0x210(r31)
stw r3, 0x214(r31)
addi r4, r1, 0x110
li r5, 1
li r6, 0 ; NudgeTo: repeated corrections must preserve controller state
cmpwi r7, 2
bne HBPlayerCallMatrix
li r6, 1 ; Only the explicit single recovery warp refreshes physics.
HBPlayerCallMatrix:
bctrl
lwz r0, 0x144(r1)
cmpwi r0, 1
beq HBPlayerDone
li r0, 2
stw r0, 0x14(r31)
b HBPlayerDone
HBPlayerInvalid:
li r0, -1
stw r0, 0x14(r31)
HBPlayerDone:
lfd f13, 0xF8(r1)
lfd f12, 0xF0(r1)
lfd f11, 0xE8(r1)
lfd f10, 0xE0(r1)
lfd f9, 0xD8(r1)
lfd f8, 0xD0(r1)
lfd f7, 0xC8(r1)
lfd f6, 0xC0(r1)
lfd f5, 0xB8(r1)
lfd f4, 0xB0(r1)
lfd f3, 0xA8(r1)
lfd f2, 0xA0(r1)
lfd f1, 0x98(r1)
lfd f0, 0x90(r1)
lwz r0, 0x8C(r1)
.int 0x7C0FF120
lwz r0, 0x88(r1)
mtctr r0
lwz r0, 0x84(r1)
mtlr r0
.int 0xB861000C
lwz r0, 0x08(r1)
addi r1, r1, 0x160
blr ; Return to the wrapper after the original transform sync.
{{PLAYER_TICK}} = b HBPlayerTick

; Reproduce the live-verified seven-word Actor::setOpacity function. Keep
; native body fully hidden while a valid avatar lease owns this exact Link.
HBSetActorOpacity:
stwu r1, -0x30(r1)
stw r0, 4(r1)
stw r9, 8(r1)
stw r10, 12(r1)
.int 0x7C000026
stw r0, 16(r1)
stfd f1, 24(r1)
lis r9, HBMailbox@ha
addi r9, r9, HBMailbox@l
lwz r0, 0x1FC(r9)
cmpw r3, r0
bne HBOpacityNative
lwz r0, 0x1F4(r9)
cmpwi r0, 1
bne HBOpacityNative
lwz r0, 0x1C4(r9)
cmpwi r0, 1
beq HBOpacityLease
cmpwi r0, 2
bne HBOpacityNative
HBOpacityLease:
lwz r0, 0x1C8(r9)
lwz r10, 0x1CC(r9)
subf r0, r0, r10
cmplwi r0, 15
bgt HBOpacityNative
lis r10, HBFirstPersonZero@ha
lfs f1, HBFirstPersonZero@l(r10)
HBOpacityNative:
lwz r0, 16(r1)
.int 0x7C0FF120
lwz r10, 12(r1)
lwz r9, 8(r1)
; Original operation widths and equality semantics, including NaN behavior.
lfs f0, 0x33C(r3)
fcmpu cr0, f0, f1
beq HBOpacityDone
stfs f1, 0x33C(r3)
li r0, 1
stb r0, 0x436(r3)
HBOpacityDone:
lfd f1, 24(r1)
lwz r0, 4(r1)
addi r1, r1, 0x30
blr
{{ACTOR_OPACITY}} = b HBSetActorOpacity

; Native controller input remains available; keyboard state augments it.
HBInput:
stwu r1, -0x30(r1)
mflr r0
stw r0, 0x34(r1)
stw r3, 0x04(r1)
stw r4, 0x08(r1)
stw r5, 0x0C(r1)
stw r6, 0x10(r1)
bl import.vpad.VPADRead
stw r3, 0x14(r1)
bl HBTick
lwz r0, 0x04(r1)
cmpwi r0, 0
bne HBInputDone
lwz r4, 0x08(r1)
cmpwi r4, 0
beq HBInputDone
lis r11, HBMailbox@ha
addi r11, r11, HBMailbox@l
stw r4, 0x38(r11)
lwz r0, 0(r4)
stw r0, 0x58(r11)
lwz r0, 0x1A0(r11)
cmpwi r0, 0
beq HBInputKeyboard
; Drop GamePad touch samples while building; clicks belong to the mod.
li r0, 0
sth r0, 0x56(r4)
sth r0, 0x5E(r4)
sth r0, 0x66(r4)
li r7, 0x0FC4
lwz r0, 0(r4)
andc r0, r0, r7
stw r0, 0(r4)
lwz r0, 4(r4)
andc r0, r0, r7
stw r0, 4(r4)
lwz r0, 8(r4)
andc r0, r0, r7
stw r0, 8(r4)
HBInputKeyboard:
lwz r0, 0x198(r11)
cmpwi r0, 0
beq HBInputDone
lwz r5, 0x3C(r11)
lwz r6, 0x19C(r11)
stw r5, 0x19C(r11)
andc r7, r5, r6
andc r8, r6, r5
lwz r0, 0(r4)
or r0, r0, r5
stw r0, 0(r4)
lwz r0, 4(r4)
or r0, r0, r7
stw r0, 4(r4)
lwz r0, 8(r4)
or r0, r0, r8
stw r0, 8(r4)
lwz r0, 0x48(r11)
stw r0, 0x0C(r4)
lwz r0, 0x4C(r11)
stw r0, 0x10(r4)
lwz r0, 0x50(r11)
stw r0, 0x14(r4)
lwz r0, 0x54(r11)
stw r0, 0x18(r4)
lwz r6, 0x10(r1)
cmpwi r6, 0
beq HBInputCount
li r0, 0
stw r0, 0(r6)
HBInputCount:
li r3, 1
stw r3, 0x14(r1)
HBInputDone:
lwz r3, 0x14(r1)
lwz r0, 0x34(r1)
mtlr r0
addi r1, r1, 0x30
blr
{{INPUT}} = bla HBInput

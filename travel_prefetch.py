"""Choose fresh Minecraft terrain demand without authorizing movement."""
import math
def position_for_terrain(native,mc,*,now_ms,heartbeat,teleport,anchor,anchor_epoch):
    if anchor is None or anchor_epoch!=teleport or not mc or not 0<=now_ms-heartbeat<=500:return native
    flags=mc['flags'];ack=mc['teleport_ack']
    if not flags&1 or flags&32 or not (ack==teleport or (not flags&256 and ack==teleport-1)):return native
    point=tuple(mc['position'])
    if len(point)!=3 or not all(math.isfinite(v) and abs(v)<20000 for v in point) or math.dist(point,anchor)>16:return native
    return point

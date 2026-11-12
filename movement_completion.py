"""The native hook clears command 3 before publishing its completion result."""
def completion(command,result,elapsed,active):
    if command!=3 and result==2:return 'complete'
    if command!=3 and result<0:return 'rejected'
    if not active:return 'released'
    if elapsed>.5:return 'stalled'
    return 'pending'

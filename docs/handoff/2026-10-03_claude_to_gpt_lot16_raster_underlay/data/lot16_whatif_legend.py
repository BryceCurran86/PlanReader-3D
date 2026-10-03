# SCRATCH what-if (no repo edit): drop non-drawing ('legend') viewport structure for the wall-scope bounds test only.
import sys, os, json, time, collections
WT = r'C:\Users\bryce\Documents\PB-PlanReader-3D\.claude\worktrees\lot16-publication'
sys.path.insert(0, WT); os.chdir(WT)
import pb_physical_wall_candidate_authority as pw
orig = pw._all_viewports
def patched(page, *, page_number):
    vps = orig(page, page_number=page_number)
    if vps is None: return None
    return [v for v in vps if getattr(v, 'view_type', None) != 'legend']
if sys.argv[2] == 'patch':
    pw._all_viewports = patched
    # also patch the helper used for resolved viewports if it calls _all_viewports internally (it does)
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
pdf = r'C:\Users\bryce\Downloads\1. Construction Plans - Lot 16 Power (REV E).pdf'
pages = [int(x)-1 for x in sys.argv[1].split(',')]
t = time.time()
claim = collect_live_physical_net_wall_claim(pdf, pages=pages)
print('elapsed', round(time.time()-t,1), flush=True)
print('claim', claim.status.value, claim.reason_codes[:14], claim.quantity_m2)
print('walls', claim.canonical_wall_status.value, claim.canonical_wall_reason_codes[:8], len(claim.canonical_walls), 'unresolved', len(claim.unresolved_wall_candidate_ids))
print('openings', len(claim.canonical_openings), collections.Counter((o.host_wall_id is not None, o.geometry_complete) for o in claim.canonical_openings))
print('rooms', claim.canonical_room_status.value, claim.canonical_room_reason_codes[:6], len(claim.canonical_rooms))
print('floors', claim.canonical_floor_status.value, claim.canonical_floor_reason_codes[:6], len(claim.canonical_floors))
print('pub reasons', list(claim.publication.reason_codes)[:12])
for o in claim.canonical_openings:
    if o.geometry_complete: print(' opening', o.page_id, o.opening_kind, o.width_m, o.height_m, o.area_m2)

"""Dev helper: send a synthetic key press to ONE X window by title (never to whatever has focus)."""
import sys
from Xlib import X, XK, display
from Xlib.protocol import event

d = display.Display()
root = d.screen().root
title, key = sys.argv[1], sys.argv[2]
ids = root.get_full_property(d.intern_atom("_NET_CLIENT_LIST"), X.AnyPropertyType).value
target = None
for wid in ids:
    w = d.create_resource_object("window", wid)
    name = w.get_wm_name() or ""
    if title in name:
        target = w
        break
if target is None:
    sys.exit(f"no window titled {title!r}")
code = d.keysym_to_keycode(XK.string_to_keysym(key))
# deliver to the deepest child (Tk's focus proxy lives below the wrapper)
def leaves(w):
    kids = w.query_tree().children
    return [w] if not kids else [x for k in kids for x in leaves(k)]
for w in [target] + leaves(target):
    for cls in (event.KeyPress, event.KeyRelease):
        ev = cls(time=X.CurrentTime, root=root, window=w, same_screen=1, child=X.NONE, root_x=0, root_y=0, event_x=0, event_y=0, state=0, detail=code)
        w.send_event(ev, propagate=True)
d.flush()
print("sent", key, "to", target.get_wm_name())

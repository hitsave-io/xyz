import _thread
import threading
from hitsave.codegraph import register_opaque

register_opaque(_thread.LockType)
register_opaque(threading.RLock)

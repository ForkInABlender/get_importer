# Written by Dylan Kenneth Eliot
import sys
import re
from browser import ajax

__all__ = ['wget', 'Github_import', 'Git_import']


# ── low-level helpers ─────────────────────────────────────────────────────────

def wget(url):
    req = ajax.Ajax()
    req.open('GET', url, False)
    req.send()
    return req


def _raw_url(username, repo, branch, path):
    return "https://raw.githubusercontent.com/{}/{}/{}/{}".format(
        username, repo, branch, path)


def _dir_of(path):
    parts = path.replace('\\', '/').split('/')
    return '/'.join(parts[:-1]) if len(parts) > 1 else ''


def _path_to_modname(path):
    """
    Convert a file path to a dotted module name.
      pkg/sub/module.py   -> pkg.sub.module
      pkg/sub/__init__.py -> pkg.sub
    """
    p = path.replace('\\', '/').rstrip('/')
    if p.endswith('.py'):
        p = p[:-3]
    if p.endswith('/__init__'):
        p = p[:-9]
    return p.replace('/', '.')


# ── relative-import resolver ──────────────────────────────────────────────────

def _relative_dep_paths(source, current_path):
    """
    Scan *source* for relative imports and return a list of
    (modname, filepath) pairs that must be pre-loaded.

    Handles:
      from .module   import Foo        -> {dir}/module.py
      from .         import foo, bar   -> {dir}/foo.py, {dir}/bar.py
      from ..utils   import Baz        -> {parent}/utils.py
    """
    base_parts = _dir_of(current_path).split('/') if _dir_of(current_path) else []
    deps = []

    # Match:  from  <dots><optional.path>  import  <names>
    pat = re.compile(
        r'^[ \t]*from[ \t]+(\.+)([\w.]*)[ \t]+import[ \t]+([^\n\\]+)',
        re.MULTILINE
    )

    for m in pat.finditer(source):
        dots      = m.group(1)           # e.g. "." or ".."
        trail     = m.group(2).strip()   # e.g. "utils" or ""
        names_raw = m.group(3).strip()

        level     = len(dots)

        # Walk up (level-1) directories
        ctx = base_parts[:max(0, len(base_parts) - (level - 1))]
        ctx_dir = '/'.join(ctx)

        def _make_entry(rel_file):
            joined = (ctx_dir + '/' + rel_file).strip('/')
            return (_path_to_modname(joined), joined)

        if trail:
            # from .utils import Foo  ->  utils.py
            deps.append(_make_entry(trail.replace('.', '/') + '.py'))
        else:
            # from . import foo, bar  ->  foo.py, bar.py
            for raw in names_raw.split(','):
                name = raw.strip().split(' ')[0].strip()   # drop "as alias"
                if name and re.match(r'^\w+$', name):
                    deps.append(_make_entry(name + '.py'))

    return deps


# ── recursive module fetcher ──────────────────────────────────────────────────

def _fetch_module(username, repo, branch, path, _visited=None):
    """
    Fetch *path* from GitHub, resolve its relative imports recursively,
    and register everything in sys.modules before exec-ing the source.
    """
    if _visited is None:
        _visited = set()

    modname = _path_to_modname(path)
    if modname in sys.modules or path in _visited:
        return
    _visited.add(path)

    url  = _raw_url(username, repo, branch, path)
    resp = wget(url)

    # Fallback: try package __init__.py
    if resp.status != 200 and path.endswith('.py'):
        alt  = path[:-3] + '/__init__.py'
        resp = wget(_raw_url(username, repo, branch, alt))
        if resp.status == 200:
            path    = alt
            modname = _path_to_modname(path)
        else:
            raise ImportError(
                "Cannot fetch '{}': HTTP {}".format(modname, resp.status))

    source = resp.text

    # Pre-load every relative dependency first (depth-first)
    for dep_modname, dep_path in _relative_dep_paths(source, path):
        if dep_modname not in sys.modules:
            _fetch_module(username, repo, branch, dep_path, _visited)

    # Build a minimal module object and register it *before* exec
    # so that circular references inside the module resolve correctly.
    class _Mod:
        pass

    mod              = _Mod()
    mod.__name__     = modname
    mod.__file__     = url
    mod.__package__  = modname.rpartition('.')[0]
    mod.__all__      = []
    sys.modules[modname] = mod

    exec(source, mod.__dict__)


# ── public API ────────────────────────────────────────────────────────────────

def Github_import(username, repo, branch, path_to_module):
    """Return the raw source text of a file from GitHub."""
    return wget(_raw_url(username, repo, branch, path_to_module)).text


class Git_import:
    """
    Context-manager that fetches a module *and its entire relative-import
    tree* from GitHub, then exposes its public names on *self*.

    Usage::

        with Git_import('user', 'repo', 'main', 'pkg/utils.py') as m:
            m.helper_fn()

    If the module defines ``__all__``, only those names are copied;
    otherwise every name that doesn't start with '_' is copied.
    """

    def __init__(self, username, repo, branch, path_to_module):
        self.username       = username
        self.repo           = repo
        self.branch         = branch
        self.path_to_module = path_to_module
        self.__all__        = []

    def __enter__(self):
        _fetch_module(self.username, self.repo, self.branch,
                      self.path_to_module)

        modname = _path_to_modname(self.path_to_module)
        mod     = sys.modules[modname]

        pub = getattr(mod, '__all__', None)
        for k, v in mod.__dict__.items():
            if pub is not None:
                if k in pub:
                    setattr(self, k, v)
            elif not k.startswith('_'):
                setattr(self, k, v)

        for attr in ('username', 'repo', 'branch', 'path_to_module'):
            try:
                delattr(self, attr)
            except AttributeError:
                pass

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass   # module stays in sys.modules for the session

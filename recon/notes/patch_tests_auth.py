import io

HEADER = '''
# A throwaway database per run, with one account registered in it: the server
# now refuses any digest it does not know, so the test has to own a real one.
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")
'''

def patch(path, env_old, env_new, hash_old, hash_new):
    s = io.open(path, encoding="utf-8").read()
    if "import tempfile" not in s:
        s = s.replace("import subprocess", "import subprocess\nimport tempfile", 1)
    anchor = "srv = subprocess.Popen("
    s = s.replace(anchor, HEADER.lstrip("\n") + "\n" + anchor, 1)
    s = s.replace(env_old, env_new, 1)
    s = s.replace(hash_old, hash_new)
    io.open(path, "w", encoding="utf-8").write(s)

base = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/"

patch(base + "test_world.py",
      'env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",\n'
      '           LAVA_NEWCHAR="1")',
      'env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",\n'
      '           LAVA_DB=DB)',
      'c.send("login;hash=@abc@;")',
      'c.send("login;hash=@%s@;" % CRED)')

patch(base + "test_handshake.py",
      'env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1")',
      'env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",\n'
      '           LAVA_DB=DB)',
      's.sendall(b"login;hash=@deadbeefcafe@;\x00")',
      's.sendall(("login;hash=@%s@;" % CRED).encode("cp1251") + b"\x00")')
print("ok")

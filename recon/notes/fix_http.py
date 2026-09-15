import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()

# 1. base must be an absolute URL with NO trailing slash: the client builds
#    every resource URL as base + "/avatars/list.xml", so a trailing slash
#    yields a double slash and a relative base is resolved unpredictably.
s = s.replace('  <resource base="/res/">',
              '  <resource base="http://{host}:{http_port}/res">')

# 2. print() is block-buffered when stdout is a file, so the request log
#    stayed empty while requests were in fact arriving.
s = s.replace('import os\nimport posixpath',
              'import os\nimport posixpath\nimport sys')
s = s.replace('    def log_message(self, fmt, *args):\n'
              '        print("  HTTP %s" % (fmt % args))',
              '    def log_message(self, fmt, *args):\n'
              '        print("  HTTP %s" % (fmt % args), flush=True)')

# 3. csettings now needs the http port too
s = s.replace('CSETTINGS.format(host=GAME_HOST, port=GAME_PORT), "text/xml")',
              'CSETTINGS.format(host=GAME_HOST, port=GAME_PORT,\n'
              '                                        http_port=HTTP_PORT), "text/xml")')
# the {host} inside the resource base is the HTTP host, not the game host;
# they are the same value here, so one format call covers both.

io.open(p, "w", encoding="utf-8").write(s)
print("bootstrap_http.py patched")

# client/keys

The public keys every launcher is built with (launcher/build.ps1):

- `resource.keys` -- what a release pointer is signed with. The private key
  lives on the server only (/opt/lava-ci/client/resource.pem, made by
  deploy/remote/install.sh, which prints the line to put here).
- `launcher.keys` -- what a launcher statement is signed with. The private key
  is the owner's, outside the repository and outside OneDrive
  (client/README.md, «Ключи»).

One line per key: `<keyid> <e> <n in hex>`. Every listed key is accepted, so a
key is replaced by listing both for one launcher release, then dropping the
old one. A launcher cannot be built until both files hold a key.

# client/files

Small files of ours that players get as they are, at the same path under
`res/`: `client/files/xmldocs/x.xml` becomes `res/xmldocs/x.xml`. A file here
replaces the original one at that path. A path the release also generates
(`main.swf`, `database/texts.xml`, `database/locations.xml`,
`hints/hints.xml`, the map tiles server/map_cells.py paints over, the
sprite files of the owner's objects (client/objects/), `xml/loc_defs.xml`
and the locations of ours) is refused: change its generator instead. Big
files go into the store and `client/extra.txt` (client/README.md).

A location the server should read as well -- a new place, or an original
one changed -- does not go here: it goes into `data/locations/static/<id>.xml`
(server/world.py), which the release ships at `locations/static/<id>.xml`
with its row in `xml/loc_defs.xml`, and the server reads before the
original's. An id that is both here and there stops the build.

`locations/static/262.xml` is the original file of the place «Тотем» near
Абри (Q_Abri_Totem, 5864,1838) byte for byte, but for its title: the client
writes a place's title over its window, and the original's is «Пустошь»
(the owner's Абри, 2026-10-12: «тотем - это пустоши»). It is the first file
here inside the slice of the client the server reads (deploy/deploy.sh,
README «Ресурсы для тестов»), and the server keeps the original's:
`deploy/deploy.sh --with-data` and `--data-only` refuse, before they touch
the host, a client whose copy of a slice path this folder has is not the
original's bytes by client/base.txt -- as an installed client is once the
launcher has put this release in it (tools/test_deploy_slice.py). Put the
original back from LAVA.zip, or point `LAVA_RES_SRC` at a res that has it.
server/test_abri_world.py holds this copy to client/base.txt's original but
for `title`, and takes either file from the res the server reads.

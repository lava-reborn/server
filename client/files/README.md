# client/files

Small files of ours that players get as they are, at the same path under
`res/`: `client/files/xmldocs/x.xml` becomes `res/xmldocs/x.xml`. A file here
replaces the original one at that path. A path the release also generates
(`main.swf`, `database/texts.xml`, `database/locations.xml`,
`hints/hints.xml`, and the map tiles server/map_cells.py paints over) is
refused: change its generator instead. Big files go
into the store and `client/extra.txt` (client/README.md).

`locations/static/262.xml` is the original file of the place «Тотем» near
Абри (Q_Abri_Totem, 5864,1838) byte for byte, but for its title: the client
writes a place's title over its window, and the original's is «Пустошь»
(the owner's Абри, 2026-10-12: «тотем - это пустоши»). The server reads the
installed res and keeps «Пустошь» there; server/test_abri_world.py holds
the copy to differ from the original in `title` alone.

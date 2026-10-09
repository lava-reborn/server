# client/files

Small files of ours that players get as they are, at the same path under
`res/`: `client/files/xmldocs/x.xml` becomes `res/xmldocs/x.xml`. A file here
replaces the original one at that path. A path the release also generates
(`main.swf`, `database/texts.xml`, `database/locations.xml`,
`hints/hints.xml`, and the map tiles server/map_cells.py paints over) is
refused: change its generator instead. Big files go
into the store and `client/extra.txt` (client/README.md).

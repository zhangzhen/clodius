import clodius.tiles.cooler as hgco
import json
import numpy as np
import os.path as op


def test_cooler_info():
    filename = op.join(
        'data', 'Dixon2012-J1-NcoI-R1-filtered.100kb.multires.cool')

    info = hgco.tileset_info(filename)

    tiles = hgco.generate_tiles(filename, ['a.0.0.0'])

    import base64
    r = base64.decodestring(tiles[0][1]['dense'].encode('utf-8'))
    q = np.frombuffer(r, dtype=np.float32)

    q = q.reshape((256, 256))

    filename = op.join('data', 'hic-resolutions.cool')
    # print(hgco.tileset_info(filename))


def test_cooler_tiles():
    filename = op.join('data', 'hic-resolutions.cool')
    hgco.tiles(filename, ['x.0.0.0'])

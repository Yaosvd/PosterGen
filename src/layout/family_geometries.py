"""Bounded geometry generators for mixed spanning-band/column families.

The shared search engine owns seeded sampling, validity checks and fitting.
These callbacks only reshape registered paper-free regions.
"""

from copy import deepcopy


def _reshape(zones, boxes):
    originals = {zone['zone_id']: zone for zone in zones}
    return [{**deepcopy(originals[zone_id]), 'x': x, 'y': y,
             'width': width, 'height': height, **extra}
            for zone_id, x, y, width, height, extra in boxes]


def framed_multicolumn_variants(zones, *, random_seed):
    variants = []
    gap = .025
    for opening in (.16, .20, .24):
        for closing in (.14, .18, .22):
            top, bottom = opening + gap, 1 - closing
            height = bottom - gap - top
            ids = ('body_left', 'body_middle', 'body_right')
            width = (1 - .02 * (len(ids) - 1)) / len(ids)
            boxes = [('overview', 0, 0, 1, opening, {})]
            boxes.extend((zone_id, index * (width + .02), top, width, height, {})
                         for index, zone_id in enumerate(ids))
            boxes.append(('conclusion', 0, bottom, 1, closing, {}))
            variants.append((f'frame_{opening}_{closing}_3', _reshape(zones, boxes),
                             ['resize_frame_bands', 'body_columns_3']))
    return variants


def narrative_evidence_grid_variants(zones, *, random_seed):
    variants = []
    gap = .025
    for rail in (.28, .32, .36):
        for closing in (.16, .20, .24):
            body = 1 - closing - gap
            left = rail + gap
            width = (1 - left - gap) / 2
            for fraction in (.46, .54):
                upper = (body - gap) * fraction
                lower_y = upper + gap
                boxes = [('narrative_rail', 0, 0, rail, body, {})]
                for row, (y, height) in enumerate(((0, upper), (lower_y, body - lower_y)), 1):
                    boxes.extend((f'evidence_{row}_{column+1}', left + column * (width + gap),
                                  y, width, height, {}) for column in range(2))
                boxes.append(('conclusion', 0, body + gap, 1, closing, {}))
                variants.append((f'evidence_{rail}_{closing}_{fraction}', _reshape(zones, boxes),
                                 ['resize_narrative_rail', 'redistribute_evidence_grid']))
    return variants


def central_evidence_band_variants(zones, *, random_seed):
    variants = []
    gap = .025
    for top in (.20, .24, .28):
        for band in (.34, .40, .46):
            band_y = top + gap
            bottom_y = band_y + band + gap
            boxes = [('top_left', 0, 0, .49, top, {}),
                     ('top_right', .51, 0, .49, top, {}),
                     ('central_evidence', 0, band_y, 1, band, {})]
            boxes.extend((zone_id, index * .34, bottom_y, .32, 1 - bottom_y, {})
                         for index, zone_id in enumerate(('bottom_left', 'bottom_middle', 'bottom_right')))
            variants.append((f'central_band_{top}_{band}', _reshape(zones, boxes),
                             ['resize_central_evidence_band', 'redistribute_surrounding_rows']))
    return variants

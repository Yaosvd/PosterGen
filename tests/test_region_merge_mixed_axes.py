"""Row-major matrix merging preserves consecutive reading positions."""
from src.layout.families import LayoutFamilyRegistry, valid_family_topology
from src.layout.feasibility import generate_zone_variants


def test_matrix_does_not_merge_vertical_nonconsecutive_reading_regions():
    family = LayoutFamilyRegistry().get('small_multiples_matrix')
    variants = generate_zone_variants(family, random_seed=20261028, maximum=12)
    merged = [v for v in variants if 'span_adjacent_zones' in v['mutation_trace']]
    assert merged
    for variant in merged:
        assert 'vertical' not in variant['mutation_trace']
        assert valid_family_topology(family, variant['zones'])
        for zone in variant['zones']:
            if zone.get('merged_from'):
                indices = sorted(family.contract.reading_route.index(mid) for mid in zone['merged_from'])
                assert indices[1] == indices[0] + 1

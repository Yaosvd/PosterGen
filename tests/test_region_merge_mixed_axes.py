"""One variant can contain horizontal and vertical disjoint merges together."""
from src.layout.families import LayoutFamilyRegistry, valid_family_topology
from src.layout.feasibility import generate_zone_variants


def test_same_variant_contains_one_horizontal_and_one_vertical_merge():
    family = LayoutFamilyRegistry().get('small_multiples_matrix')
    variants = generate_zone_variants(family, random_seed=20261028, maximum=12)
    mixed = [v for v in variants if 'horizontal' in v['mutation_trace']
             and 'vertical' in v['mutation_trace']
             and v['mutation_trace'].count('span_adjacent_zones') == 2]
    assert mixed
    for variant in mixed:
        assert valid_family_topology(family, variant['zones'])
        merged = [z for z in variant['zones'] if z.get('merged_from')]
        assert len(merged) == 2
        assert not set(merged[0]['merged_from']) & set(merged[1]['merged_from'])
        assert all(z['capacity'] == 2 for z in merged)

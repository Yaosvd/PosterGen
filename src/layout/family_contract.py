"""Paper-free family rules consumed by shared search and reading-flow code."""

from dataclasses import dataclass, asdict
from typing import Tuple


@dataclass(frozen=True)
class FamilyContract:
    version: int = 2
    reading: str = "columns"
    geometry: str = "generic"
    required_zones: Tuple[str, ...] = ()
    fixed_zone_ids: bool = False
    allow_split: bool = True
    allow_span: bool = True
    allow_mirror: bool = True
    protected_spans: Tuple[str, ...] = ()
    conditional_roles: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()
    sequence_check: bool = False
    peer_balance: bool = False
    # Content grouping is independent of geometry split/span permissions.
    # Extensions must opt in explicitly; text styling remains shared.
    allow_module_grouping: bool | None = None
    focus_roles: Tuple[str, ...] = ('method', 'theory', 'results', 'evaluation', 'insight')
    # Only explicitly declared findings may precede the ordinary body sequence.
    entry_roles: Tuple[str, ...] = ()

    def __post_init__(self):
        if self.version != 2 or self.reading not in {
            "neutral", "columns", "bands", "anchor_first", "parallel",
            "matrix", "spine", "stages", "framed_columns",
        }:
            raise ValueError("Unsupported layout-family contract")
        roles = {'method', 'theory', 'results', 'evaluation', 'insight',
                 'conclusion', 'impact', 'implications', 'discussion'}
        if (not self.focus_roles or set(self.focus_roles) - roles
                or any(role not in {'results', 'conclusion', 'implications'} for role in self.entry_roles)):
            raise ValueError('Invalid focus or exceptional entry policy')

    def to_dict(self):
        return asdict(self)


def ordered_zones(zones, contract):
    """Presentation traversal, not a claim about chronology or causality."""
    if contract.reading == 'framed_columns':
        # Full-width regions separate column groups. Finish each column,
        # including local split zones, before advancing to the next column.
        # In particular a bottom full-width conclusion must never be read
        # immediately after a left rail merely because both start at x=0.
        bands = sorted((zone for zone in zones
                        if float(zone['width']) >= 1 - 1e-6),
                       key=lambda zone: (float(zone['y']), zone['zone_id']))
        remaining = [zone for zone in zones if float(zone['width']) < 1 - 1e-6]
        result = []
        column_key = lambda zone: (float(zone['x']), float(zone['y']), zone['zone_id'])
        for band in bands:
            before = [zone for zone in remaining
                      if float(zone['y']) + float(zone['height']) <= float(band['y']) + 1e-6]
            result.extend(sorted(before, key=column_key))
            result.append(band)
            before_ids = {zone['zone_id'] for zone in before}
            remaining = [zone for zone in remaining if zone['zone_id'] not in before_ids]
        result.extend(sorted(remaining, key=column_key))
        return result
    if contract.entry_roles:
        columns = contract.reading in {'neutral', 'columns', 'stages', 'anchor_first', 'spine'}
        physical = sorted(zones, key=lambda z: (
            float(z['x'] if columns else z['y']),
            float(z['y'] if columns else z['x']), z['zone_id']))
        return sorted(physical, key=lambda z: z.get('role') != 'hero')
    if contract.reading == "neutral":
        # Unknown grammars receive conservative physical traversal, never a pass.
        return sorted(zones, key=lambda z: (float(z['x']), float(z['y']), z['zone_id']))
    if contract.reading in {"columns", "stages"}:
        return sorted(zones, key=lambda z: (float(z['x']), float(z['y']), z['zone_id']))
    if contract.reading in {'anchor_first', 'spine'}:
        return sorted(zones, key=lambda z: (float(z['x']), float(z['y']), z['zone_id']))
    if contract.reading == "parallel":
        return sorted(zones, key=lambda z: (
            z.get('role') == 'conclusion', float(z['x']), float(z['y']), z['zone_id']))
    return sorted(zones, key=lambda z: (float(z['y']), float(z['x']), z['zone_id']))

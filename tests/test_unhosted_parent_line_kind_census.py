"""Parent-line kind census is fail-closed and never grants a host."""
from pb_unhosted_parent_line_kind_census import census_unhosted_parent_line_kinds


def test_module_exports_census_entry_point():
    assert callable(census_unhosted_parent_line_kinds)

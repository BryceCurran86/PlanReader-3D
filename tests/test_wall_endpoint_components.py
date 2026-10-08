from pb_wall_endpoint_components import exact_endpoint_components


def test_exact_transitive_wall_endpoint_ownership():
    ids = ('a', 'b', 'c')
    endpoints = {'a': {(1.0, 2.0)}, 'b': {(1.0, 2.0)}, 'c': {(1.000001, 2.0)}}
    assert exact_endpoint_components(ids, endpoints) == {
        'a': frozenset(('a', 'b')),
        'c': frozenset(('c',)),
    }

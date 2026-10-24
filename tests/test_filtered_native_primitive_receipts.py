from pb_filtered_native_primitive_receipts import filtered_native_primitive_receipts


def line(i, **changes):
    value = {
        "id": f"d{i}i0", "kind": "line", "path_index": i,
        "x1": 0, "y1": 0, "x2": i, "y2": 1,
    }
    value.update(changes)
    return value


def test_read_only_candidate_and_determinism():
    first, second = line(50048), line(50507)
    observed = filtered_native_primitive_receipts([second, first], [first])
    assert len(observed) == 1
    assert observed[0].source_id == "d50507i0"
    assert observed[0].status == "FILTERED_NATIVE_CANDIDATE_ONLY"
    assert filtered_native_primitive_receipts([first, second], [first]) == observed


def test_foreign_or_mutated_retained_abstains():
    assert filtered_native_primitive_receipts([line(1)], [line(2)]) == ()
    assert filtered_native_primitive_receipts([line(1)], [line(1, x2=99)]) == ()
    assert filtered_native_primitive_receipts([line(1)], [line(1), line(1)]) == ()


def test_ambiguous_or_nonfinite_lines_not_claimed():
    assert filtered_native_primitive_receipts([line(1), line(1)], []) == ()
    assert filtered_native_primitive_receipts([line(1, x2=float("nan"))], []) == ()
    assert filtered_native_primitive_receipts([line(1, x2=0, y2=0)], []) == ()
    assert filtered_native_primitive_receipts([line(1, id=" ")], []) == ()

"""A catalogue preview prices only the linked original-source quantity."""
from dataclasses import replace

from pb_takeoff_output_authority import TakeoffOutputRow
from pb_vr_live_costing import CatalogueRateBinding
from pb_vr_live_costing_wsgi import make_vr_live_costing_wsgi_app
from test_vr_editor_command_preview import _fixture
from test_vr_live_costing import _book
from test_vr_live_costing_wsgi import _request


def _catalogue_app(**row_changes):
    user, ws, ledger, command = _fixture()
    obj = ledger.get_object("wall-1")
    obj.dependent_quantity_ids.append("q-finish")
    for owner in ws.objects:
        if "q-finish" not in owner.dependent_quantity_ids:
            owner.dependent_quantity_ids.append("q-finish")
    row = TakeoffOutputRow(
        quantity_id="q-finish", description="Floor or wall finish area", value=9.6, unit="m2",
        source_page=obj.source_page, source_sheet=obj.source_sheet, geometry_ref=obj.object_id,
        revision_hash=obj.revision_hash, is_publishable=True,
    )
    row = replace(row, **row_changes)
    calls = []
    book = _book(ws)
    binding = CatalogueRateBinding("paint-sage", "q-finish", command["targetCanonicalId"],
                                   book.revision, book.bindings[0].rate, ("material-binding",))

    def rate(principal, workspace, item_id, actual):
        calls.append(actual.quantity_id)
        return binding if item_id == binding.catalogue_item_id else None

    app = make_vr_live_costing_wsgi_app(
        lambda _: user, lambda *_: ws, lambda *_: (ledger, (row,)),
        lambda *_: True, lambda *_: book, load_catalogue_rate=rate,
    )
    request = {key: command[key] for key in (
        "workspaceId", "projectId", "documentId", "revisionId", "snapshotId", "sourceSha256",
    )}
    request.update(
        requestId="request-1", modelRevision=command["baseModelRevision"],
        canonicalObjectId=command["targetCanonicalId"], objectId=command["targetObjectId"],
        objectRevision=command["targetRevisionHash"], catalogueItemId="paint-sage", quantityId=row.quantity_id,
    )
    return app, request, calls, ledger


_ROUTE = "/api/editor/workspaces/w1/costing/catalogue"


def test_catalogue_cost_receipt_reuses_original_amount_and_server_rate():
    app, request, calls, ledger = _catalogue_app()
    status, _, price = _request(app, request, path=_ROUTE)
    assert status.startswith("200"), price
    assert price["quantity"] == "9.6" and price["currency"] == "AUD"
    assert price["commercialPublicationAllowed"] is False
    assert price["previewOnly"] is True and price["rateBookRevision"]
    assert calls == ["q-finish"]
    assert ledger.events == ()


def test_catalogue_cost_refuses_stale_rows_browser_amounts_and_unknown_rate():
    for changes, overrides in [
        ({"is_publishable": False}, {}), ({"revision_hash": "old"}, {}),
        ({"geometry_ref": "other-object"}, {}), ({}, {"amount": 1}),
        ({}, {"catalogueItemId": "different"}),
    ]:
        app, request, calls, _ = _catalogue_app(**changes)
        status, _, price = _request(app, {**request, **overrides}, path=_ROUTE)
        assert status.startswith("409") and "priceIncTax" not in price, price
        assert bool(calls) == ("catalogueItemId" in overrides)

"""Client-reported supplier order, delivery, invoice, receipt and cash ledger.

The original procurement plan contains DRAFT orders. An event declaring an
order sent is NOT an external vendor transmission from this tool.
This module never certifies bank payment, delivered construction, original
source quantities or benchmark accuracy.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
from typing import Any, Mapping

from tools.gpt3_client_procurement_awards import _date, _hash, _id, _amount, _positive
from tools.gpt3_verified_customer_quote import _csv_text, _decimal, _money, _number, _write_new
from tools.report_gpt3_four_project_evidence import _read_json_without_duplicate_keys


def build_procurement_receipts(plan: dict, book: dict) -> dict:
    if (type(plan) is not dict
        or plan.get("schema_version") != "gpt3-client-procurement-awards-v1"
        or plan.get("procurement_fingerprint") != _hash(plan, "procurement_fingerprint")):
        raise ValueError("source quote procurement plan has invalid identity or fingerprint")
    if (type(book) is not dict
        or book.get("schema_version") != "gpt3-client-procurement-events-v1"
        or book.get("procurement_fingerprint") != plan["procurement_fingerprint"]):
        raise ValueError("supplier event book must bind exact source procurement plan")
    events = book.get("events")
    if type(events) is not list:
        raise ValueError("supplier event log must be an explicit chronological list")
    ordered = {}
    for order in plan["purchase_order_drafts"]:
        pid = order["po_draft_id"]
        if pid in ordered:
            raise ValueError("duplicate purchase order draft identity")
        ordered[pid] = order
    lines = {}
    for pid, order in ordered.items():
        for line in order["lines"]:
            key = (pid, line["requisition_id"])
            if key in lines:
                raise ValueError("purchase order repeats a requisition")
            lines[key] = {
                "po_draft_id": pid,
                "requisition_id": line["requisition_id"],
                "supplier_id": order["supplier_id"],
                "purchase_unit": line["purchase_unit"],
                "ordered_quantity": line["purchase_quantity"],
                "accepted_receipt_quantity": Decimal("0"),
                "rejected_delivery_quantity": Decimal("0"),
                "returned_after_acceptance_quantity": Decimal("0"),
                "invoiced_gross": Decimal("0"),
                "paid_gross": Decimal("0"),
                "ordered_gross": Decimal(line["gross_cost"]),
                "source_quantity_ids": line["related_signed_quantity_ids"],
            }
    sent = {}
    notices = {}
    receipt_refs = set()
    invoice_refs = set()
    payment_refs = set()
    invoices = {}
    payments = []
    audit = []
    previous_hash = plan["procurement_fingerprint"]
    last_date = None

    for index, row in enumerate(events):
        if type(row) is not dict:
            raise ValueError("procurement ledger event must be an object")
        kind = row.get("event")
        pid = _id(row.get("po_draft_id"), "event purchase order")
        if pid not in ordered:
            raise ValueError("event references unknown draft purchase order")
        when = _date(row.get("recorded_on"), "procurement event date")
        if last_date is not None and when < last_date:
            raise ValueError("supplier events must be chronological")
        last_date = when
        reference = _id(row.get("reference"), "external event reference")
        if kind == "RECORD_PO_SENT":
            if pid in sent:
                raise ValueError("purchase order cannot be transmitted twice")
            sender = _id(row.get("recorded_by"), "client purchase sender")
            sent[pid] = {"on": when.isoformat(), "reference": reference,
                         "recorded_by": sender}
        else:
            if pid not in sent:
                raise ValueError("supplier delivery or invoice cannot precede client-recorded order")
        if kind == "SHIPMENT_NOTICE":
            key = (pid, _id(row.get("requisition_id"), "shipment requisition"))
            if key not in lines:
                raise ValueError("shipment notice belongs to unknown ordered line")
            qty = _positive(row.get("shipped_quantity"), "supplier announced shipment quantity")
            existing = notices.get(key, Decimal("0"))
            state = lines[key]
            # Replacements of already rejected/returned supplier goods are
            # allowed; they are still NOT extra client purchase demand.
            replacement_allowance = (
                state["rejected_delivery_quantity"]
                + state["returned_after_acceptance_quantity"]
            )
            if existing + qty > Decimal(state["ordered_quantity"]) + replacement_allowance:
                raise ValueError("announced shipment exceeds approved order plus returned/rejected replacements")
            notices[key] = existing + qty
        elif kind == "RECEIVE_DELIVERY":
            key = (pid, _id(row.get("requisition_id"), "receipt requisition"))
            if key not in lines:
                raise ValueError("physical receipt belongs to unknown purchase order line")
            receipt_id = _id(row.get("receipt_id"), "delivery receipt ID")
            if receipt_id in receipt_refs:
                raise ValueError("duplicate delivery receipt identity")
            receipt_refs.add(receipt_id)
            accepted = _decimal(row.get("accepted_quantity"), "accepted purchase delivery quantity")
            rejected = _decimal(row.get("rejected_quantity"), "rejected purchase delivery quantity")
            if accepted + rejected <= 0:
                raise ValueError("delivery record requires a positive handled quantity")
            state = lines[key]
            if (
                accepted + rejected > Decimal(state["ordered_quantity"])
                or (
                    state["accepted_receipt_quantity"] + accepted
                    - state["returned_after_acceptance_quantity"]
                ) > Decimal(state["ordered_quantity"])
            ):
                raise ValueError("net accepted goods exceed client-ordered quantity")
            state["accepted_receipt_quantity"] += accepted
            state["rejected_delivery_quantity"] += rejected
        elif kind == "RETURN_ACCEPTED":
            key = (pid, _id(row.get("requisition_id"), "return requisition"))
            if key not in lines:
                raise ValueError("return refers to unknown order line")
            return_id = _id(row.get("return_id"), "return reference")
            if return_id in receipt_refs:
                raise ValueError("duplicate return/receipt reference")
            receipt_refs.add(return_id)
            qty = _positive(row.get("returned_quantity"), "return quantity")
            state = lines[key]
            if qty + state["returned_after_acceptance_quantity"] > state["accepted_receipt_quantity"]:
                raise ValueError("cannot return more purchased stock than was accepted")
            state["returned_after_acceptance_quantity"] += qty
        elif kind == "SUPPLIER_INVOICE":
            invoice_id = _id(row.get("invoice_id"), "supplier invoice ID")
            if invoice_id in invoice_refs:
                raise ValueError("duplicate supplier invoice ID")
            invoice_refs.add(invoice_id)
            key = (pid, _id(row.get("requisition_id"), "supplier invoice line"))
            if key not in lines:
                raise ValueError("supplier invoice references unknown ordered line")
            invoice_amount = _positive(row.get("gross_amount"), "supplier invoice gross")
            if _money(invoice_amount) != str(row["gross_amount"]):
                raise ValueError("supplier invoice amount must be exact cents")
            state = lines[key]
            if state["accepted_receipt_quantity"] <= state["returned_after_acceptance_quantity"]:
                raise ValueError("invoice requires net accepted physical purchase receipts")
            if state["invoiced_gross"] + invoice_amount > state["ordered_gross"]:
                raise ValueError("supplier invoices exceed authorised purchase order line value")
            state["invoiced_gross"] += invoice_amount
            invoices[invoice_id] = {
                "invoice_id": invoice_id, "po_draft_id": pid,
                "requisition_id": key[1], "gross_amount": _money(invoice_amount),
                "paid": Decimal("0"), "recorded_on": when.isoformat(),
            }
        elif kind == "RECORD_SUPPLIER_PAYMENT":
            invoice_id = _id(row.get("invoice_id"), "supplier payable invoice ID")
            if invoice_id not in invoices or invoices[invoice_id]["po_draft_id"] != pid:
                raise ValueError("supplier payment requires a matching recorded invoice")
            payment_id = _id(row.get("payment_id"), "supplier payment reference")
            if payment_id in payment_refs:
                raise ValueError("supplier payment cannot reuse one receipt ID")
            payment_refs.add(payment_id)
            amount = _positive(row.get("amount"), "recorded supplier payment amount")
            if _money(amount) != str(row["amount"]):
                raise ValueError("supplier payment amount must be exact cents")
            invoice = invoices[invoice_id]
            if invoice["paid"] + amount > Decimal(invoice["gross_amount"]):
                raise ValueError("recorded supplier payment exceeds issued invoice balance")
            invoice["paid"] += amount
            key = (pid, invoice["requisition_id"])
            lines[key]["paid_gross"] += amount
            payments.append({
                "payment_id": payment_id, "invoice_id": invoice_id,
                "recorded_on": when.isoformat(), "amount": _money(amount),
                "reference": reference,
                "payment_status": "CLIENT_RECORDED_NOT_BANK_VERIFIED",
            })
        elif kind != "RECORD_PO_SENT" and kind != "SHIPMENT_NOTICE":
            raise ValueError("unknown supplier event transition")
        attestation = {
            "sequence": index, "previous_hash": previous_hash,
            "event_payload": row,
        }
        attestation["event_hash"] = _hash(attestation, "event_hash")
        previous_hash = attestation["event_hash"]
        audit.append(attestation)

    status = []
    for (pid, req), item in sorted(lines.items()):
        net = item["accepted_receipt_quantity"] - item["returned_after_acceptance_quantity"]
        pending = Decimal(item["ordered_quantity"]) - net
        if pending < 0:
            raise ValueError("net receipt unexpectedly exceeds client-approved order")
        state = "UNSENT" if pid not in sent else (
            "RECEIVED" if pending == 0 else
            "PARTIALLY_RECEIVED" if net else "AWAITING_ACCEPTED_DELIVERY"
        )
        status.append({
            "po_draft_id": pid, "requisition_id": req,
            "supplier_id": item["supplier_id"],
            "purchase_unit": item["purchase_unit"],
            "ordered_quantity": item["ordered_quantity"],
            "net_accepted_quantity": _number(net),
            "rejected_quantity": _number(item["rejected_delivery_quantity"]),
            "returned_quantity": _number(item["returned_after_acceptance_quantity"]),
            "outstanding_purchase_quantity": _number(pending),
            "source_quantity_ids": item["source_quantity_ids"],
            "invoiced_gross": _money(item["invoiced_gross"]),
            "recorded_paid_gross": _money(item["paid_gross"]),
            "unpaid_invoice_gross": _money(item["invoiced_gross"] - item["paid_gross"]),
            "ordered_gross": _money(item["ordered_gross"]),
            "status": state,
            "material_receipt_authority": "CLIENT_DECLARED_NOT_VERIFIED_DELIVERY",
        })
    invoices_out = [
        {**{k: v for k, v in inv.items() if k != "paid"},
         "paid_gross": _money(inv["paid"]),
         "outstanding_gross": _money(Decimal(inv["gross_amount"]) - inv["paid"])}
        for _, inv in sorted(invoices.items())
    ]
    total = lambda field: _money(sum((Decimal(item[field]) for item in status), Decimal("0")))
    result = {
        "schema_version": "gpt3-client-procurement-receipts-v1",
        "project_id": plan["project_id"],
        "currency": plan["currency"],
        "quote_fingerprint": plan["quote_fingerprint"],
        "signed_run_fingerprint": plan["signed_run_fingerprint"],
        "procurement_fingerprint": plan["procurement_fingerprint"],
        "client_recorded_po_transmissions": [
            {"po_draft_id": pid, **row} for pid, row in sorted(sent.items())
        ],
        "line_status": status,
        "invoices": invoices_out, "payments": payments,
        "event_chain": audit,
        "supplier_financial_summary": {
            "approved_order_line_gross": total("ordered_gross"),
            "invoiced_gross": total("invoiced_gross"),
            "recorded_paid_gross": total("recorded_paid_gross"),
            "outstanding_payable_gross": total("unpaid_invoice_gross"),
        },
        "external_orders_sent_by_this_tool": False,
        "supplier_delivery_certified": False,
        "bank_payments_verified": False,
        "signed_source_measurements_changed": False,
        "official_four_project_accuracy": None,
    }
    result["fulfillment_fingerprint"] = _hash(result, "fulfillment_fingerprint")
    return result


def fulfillment_csv(report: Mapping[str, Any]) -> str:
    keys = ("po_draft_id", "requisition_id", "supplier_id", "status",
            "purchase_unit", "ordered_quantity", "net_accepted_quantity",
            "outstanding_purchase_quantity", "rejected_quantity",
            "returned_quantity", "invoiced_gross", "recorded_paid_gross",
            "unpaid_invoice_gross", "source_quantity_ids")
    result = io.StringIO(newline="")
    writer = csv.DictWriter(result, fieldnames=keys)
    writer.writeheader()
    for line in report["line_status"]:
        row = dict(line)
        row["source_quantity_ids"] = ";".join(row["source_quantity_ids"])
        writer.writerow({key: (
            _csv_text(row.get(key)) if key in (
                "po_draft_id", "requisition_id", "supplier_id", "status",
                "purchase_unit", "source_quantity_ids"
            ) else row.get(key)
        ) for key in keys})
    return result.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--procurement", required=True, type=Path)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    args = parser.parse_args(argv)
    plan = _read_json_without_duplicate_keys(args.procurement)
    events = _read_json_without_duplicate_keys(args.events)
    result = build_procurement_receipts(plan, events)
    body = (fulfillment_csv(result) if args.format == "csv" else
            json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")
    _write_new(args.output, body, (args.procurement, args.events))
    print(json.dumps({
        "purchase_lines": len(result["line_status"]),
        "supplier_invoice_count": len(result["invoices"]),
        "payment_receipt_count": len(result["payments"]),
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

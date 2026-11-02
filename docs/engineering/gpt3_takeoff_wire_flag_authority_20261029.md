# GPT3 — Exact Boolean publishing wire and finite source confidence (2026-10-29)

## Observed real producer-to-customer contract

Main `98ce4bd77488894e7d13e4153b34197ef3205f58`: generic `pb_takeoff_output_authority.TakeoffOutputRow.from_dict` applies `bool(data.get("is_publishable", False))`. A wire value `"false"` is a nonempty string and becomes `True`, and a later legacy preflight sees a typed `TakeoffOutputRow` with `is_publishable=True`, so it bypasses the gate's explicit JSON Boolean check that applies only to direct dictionary inputs. Matching FIRM/status/trace fields can then construct a commercially ready JobHub payload from a self-proclaimed flag. Separately `TakeoffOutputRow.__post_init__` rejects confidence <0 or >1 but NaN satisfies neither comparison, so nonfinite source confidence is accepted.

## Fix

Require a concrete `bool` wire receipt for `is_publishable` when present; when absent preserve the safe historical default `False`. Reject all coercible strings, floats, ints, None and containers instead of guessing publishability. Require `math.isfinite(confidence)` as well as the existing [0,1] bounds at construction/deserialization. Preserve genuinely approved factory/serialized rows, revision/project gates, original measured quantity, real customer material/price and original row hash schema. Do not add approval authority.

## Actual consumer regression and scope

New tests assert adversarial flag/NaN/±inf rejects; missing false remains unpublishable; valid explicit Boolean TRUE still passes `run_jobhub_publish_preflight` and `build_jobhub_payload`; false remains noncommercial/draft. Synthetic mechanical tests ONLY, not original PDF/FIRM authenticated quantities or frozen 120 scoring. No changes to original PDFs/tokens, archived signed eight/customer, frozen truth/scorer, 20,000 primitive cap, 2.5 pt snap, #3796 original-positive release, GPT1/2/MAX/AntiGravity/Claude source code. Exact-head dual Python3.13/3.14 CI plus signed/customer/raster/performance gates and technical review required.

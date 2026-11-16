# Real PlanReader workspace → VR review scene

In the existing Streamlit app, open a workspace, then choose **Editable 3D
Inspector → Real workspace objects**. Under the 3D plot, expand **Download a
3D / VR review scene (unverified source)**, select the uploaded source PDF and
download the JSON. The chosen PDF must have a recorded SHA-256 in the
workspace's `documents` table.

Import this JSON in the standalone `vr-editor` viewer (currently the
read-only React/WebXR draft). It shows the existing model masses as reviewable
wall faces or source plan lines. It will **not** show trusted green geometry,
permit editing, or publish quantities. The selected document hash is a
document-identity reference, not proof that every mass derives from that PDF.

The exporter reuses:

- `_load_real_workspace_objects` and the existing persisted correction replay
- `Editable3DCorrectionLedger.get_object` for the actual corrected objects
- `pb_vr_editor_scene_manifest.compile_editor_scene` for the established DTO

It never invents canonical IDs, original PDF path ownership, wall thickness or
a missing height; `canonical_object_ids={}`, no source-native witnesses,
and `canEdit=false` for every object. It performs no database modifications,
uploads or commercial changes. The user must explicitly click Download.

Limitations: current `model_masses` has no native source-path foreign key to
the chosen PDF, so this route is **not** the required original-to-customer
PlanReader authority proof. Authenticated server-hosted VR and approved
recalculations remain separate follow-up work.

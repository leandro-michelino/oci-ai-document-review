#!/usr/bin/env python3
"""Generate editable OCI diagrams from the official Oracle toolkit, plus source coverage."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs/assets"
STEM = "oci-ai-document-review-architecture"


def load_builder(skill_dir):
    path = skill_dir / "scripts/ocidraw.py"
    if not path.is_file():
        raise SystemExit(
            "Install the oci-architecture-diagrams skill or set OCI_DIAGRAM_SKILL."
        )
    spec = importlib.util.spec_from_file_location("ocidraw", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.Diagram


class Architecture:
    def __init__(self, diagram_type):
        self.diagram_type = diagram_type
        self.pages = []
        self.resources = {}
        self.evidence = {}

    def page(self, slug, title, subtitle):
        d = self.diagram_type(title=title)
        original_id = d._id
        d._id = lambda: slug + "_" + original_id()
        original_vertex = d._vertex

        def vertex(identifier, value, style, *args, **kwargs):
            if value and not style.startswith("text;"):
                style += "fontSize=13;"
            return original_vertex(identifier, value, style, *args, **kwargs)

        d._vertex = vertex
        d.slug = slug
        d.text(title, 30, 20, 1450, 40, size=24, bold=True)
        d.text(subtitle, 30, 70, 1450, 30, size=13)
        self.pages.append(d)
        return d

    def resource(self, node, *refs):
        self.resources[node.id] = list(refs)
        return node

    def edge(self, d, a, b, label, evidence, **kwargs):
        if route := kwargs.get("waypoints"):
            start = d._anchor(a, kwargs.get("exit"))
            end = d._anchor(b, kwargs.get("entry"))
            route = list(route)
            if start[0] != route[0][0] and start[1] != route[0][1]:
                route.insert(0, (route[0][0], start[1]))
            if end[0] != route[-1][0] and end[1] != route[-1][1]:
                if kwargs.get("entry", (0.5, 0.5))[1] in (0, 1):
                    route.append((end[0], route[-1][1]))
                else:
                    route.append((route[-1][0], end[1]))
            kwargs["waypoints"] = route
        edge = d.connect(a, b, label=label, **kwargs)
        self.evidence[edge] = evidence
        return edge

    def save(self):
        document = ET.Element("mxfile", host="ocidraw", type="device")
        declared = set()
        for path in (ROOT / "terraform").glob("*.tf"):
            declared.update(
                f"{kind}.{name}"
                for kind, name in re.findall(
                    r'resource\s+"([^"]+)"\s+"([^"]+)"', path.read_text()
                )
            )
        covered = {ref for refs in self.resources.values() for ref in refs}
        if missing := declared - covered:
            raise ValueError(
                f"Terraform resources missing from diagram: {sorted(missing)}"
            )
        if unexpected := covered - declared:
            raise ValueError(
                f"Diagram resources absent from Terraform: {sorted(unexpected)}"
            )
        report = {
            "toolkit": "Oracle OCI Architecture Diagram Toolkit v24.2",
            "pages": [],
            "declared_resources": sorted(declared),
            "unrepresented_resources": [],
        }
        for d in self.pages:
            if warnings := d.check():
                raise ValueError(f"{d.slug}: {warnings}")
            page = ET.fromstring(d.xml()).find("diagram")
            page.set("id", d.slug)
            cells = page.findall(".//mxCell")
            identifiers = {cell.get("id") for cell in cells}
            if len(identifiers) != len(cells):
                raise ValueError(f"Duplicate cell IDs on {d.slug}")
            connections = []
            for cell in cells:
                if refs := self.resources.get(cell.get("id")):
                    cell.set("resourceRefs", " ".join(refs))
                if cell.get("edge") == "1":
                    if (
                        cell.get("source") not in identifiers
                        or cell.get("target") not in identifiers
                    ):
                        raise ValueError("Connector references a missing endpoint")
                    source = self.evidence[cell.get("id")]
                    cell.set("sourceEvidence", source)
                    connections.append(
                        {
                            key: cell.get(key)
                            for key in (
                                "id",
                                "source",
                                "target",
                                "value",
                                "style",
                                "sourceEvidence",
                            )
                        }
                    )
            report["pages"].append(
                {
                    "id": d.slug,
                    "title": d.title_text,
                    "layout_warnings": [],
                    "connections": connections,
                }
            )
            document.append(page)
        ASSETS.mkdir(parents=True, exist_ok=True)
        ET.indent(document)
        ET.ElementTree(document).write(
            ASSETS / f"{STEM}.drawio", encoding="utf-8", xml_declaration=True
        )
        (ROOT / "docs/architecture_connections.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(
            f"Generated {len(self.pages)} pages, {len(declared)} Terraform resources, "
            f"{len(self.evidence)} source-backed connections; layout checks passed."
        )


def build(skill_dir):
    a = Architecture(load_builder(skill_dir))
    d = a.page(
        "processing",
        "OCI AI Document Review | Document processing",
        "Logical data flow. OCI API calls originate in the VM worker. Arrow labels describe application behavior.",
    )
    user = d.icon("User", 90, 270, label="Business reviewer", label_pos="top")
    portal = d.box(
        "Streamlit portal\nUpload 1–5 files\nShared expense/reference",
        240,
        210,
        240,
        120,
    )
    worker = d.box(
        "VM worker pool\nMAX_PARALLEL_JOBS\nLocal source preserved", 620, 210, 260, 120
    )
    bucket = a.resource(
        d.icon(
            "OCI Object Storage",
            1180,
            270,
            label="Private Object Storage\nOriginals + compliance catalog",
            label_pos="top",
        ),
        "oci_objectstorage_bucket.documents",
    )
    lifecycle = a.resource(
        d.box(
            "Bucket lifecycle\ndocuments/: 30 days by default\ncompliance/ remains outside expiry",
            1050,
            370,
            360,
            100,
        ),
        "oci_objectstorage_object_lifecycle_policy.documents_retention",
    )
    service_policy = a.resource(
        d.box(
            "Regional lifecycle service IAM\nRoot policy: this bucket only\n60s IAM propagation wait",
            1100,
            540,
            320,
            110,
        ),
        "oci_identity_policy.object_lifecycle_service",
        "time_sleep.lifecycle_policy_propagation",
    )
    a.edge(
        d,
        service_policy,
        lifecycle,
        "Authorizes delete lifecycle",
        "terraform/object_storage.tf:object_lifecycle_service,lifecycle_policy_propagation",
        kind="plain",
        exit=(0.5, 0),
        entry=(0.5, 1),
    )
    local = d.box(
        "Local text extraction\nText files / fully text-native PDFs", 500, 500, 260, 100
    )
    du = d.icon(
        "Document Understanding",
        1020,
        550,
        label="Document Understanding\nImages / scans / mixed PDFs\nChunked OCR + text fallback",
        label_pos="top",
    )
    context = d.box(
        "Extracted context in worker\nText + fields + table count\nPrivacy assessment",
        740,
        760,
        260,
        110,
    )
    genai = d.icon(
        "OCI Generative AI",
        1280,
        815,
        label="OCI Generative AI\nGENAI_REGION\nStructured review",
        label_pos="top",
    )
    compliance = d.box(
        "Worker post-processing\nCompliance catalog overlay\nSafety block → manual review",
        1160,
        1030,
        260,
        110,
    )
    metadata = d.box(
        "VM-local review data\nJSON + Markdown\nWorkflow + audit + source copy",
        740,
        1030,
        260,
        110,
    )
    actions = d.box(
        "Actions + Reviewed\nHuman approve/reject\nAssignment, comments, retry",
        240,
        1030,
        260,
        110,
    )
    a.edge(
        d,
        user,
        portal,
        "Upload / review",
        "app.py:upload_page,render_review_action_panel",
        kind="dashed",
    )
    a.edge(d, portal, worker, "Queue", "src/job_queue.py:submit_document_processing")
    a.edge(
        d,
        worker,
        bucket,
        "Upload original; load catalog",
        "src/processor.py:process; src/compliance.py:load_compliance_catalog",
    )
    a.edge(
        d,
        bucket,
        lifecycle,
        "Lifecycle association",
        "terraform/object_storage.tf:documents_retention",
        kind="plain",
        exit=(0.5, 1),
        entry=(0.36, 0),
    )
    a.edge(
        d,
        worker,
        local,
        "Text-native path",
        "src/text_extraction.py:extract_text_locally",
        exit=(0.25, 1),
        entry=(0.5, 0),
        waypoints=[(685, 430), (630, 430)],
    )
    a.edge(
        d,
        worker,
        du,
        "Analyze object reference",
        "src/document_understanding_client.py:_extract_document_inline",
        exit=(1, 0.75),
        entry=(0, 0.5),
        waypoints=[(900, 300), (900, 550)],
    )
    a.edge(
        d,
        local,
        context,
        "Local text",
        "src/processor.py:process",
        exit=(0.5, 1),
        entry=(0.25, 0),
        waypoints=[(630, 690), (805, 690)],
    )
    a.edge(
        d,
        du,
        context,
        "OCR results via worker",
        "src/processor.py:extract_with_document_understanding",
        exit=(0.5, 1),
        entry=(0.75, 0),
        waypoints=[(1020, 690), (935, 690)],
    )
    a.edge(
        d,
        context,
        genai,
        "Prompt + context",
        "src/processor.py:process; src/genai_client.py:analyze_document",
    )
    a.edge(
        d,
        genai,
        compliance,
        "Result handled by worker",
        "src/processor.py:process",
        exit=(0.5, 1),
        entry=(0.46, 0),
    )
    a.edge(
        d,
        compliance,
        metadata,
        "Persist review",
        "src/processor.py:process",
        exit=(0, 0.5),
        entry=(1, 0.5),
    )
    a.edge(
        d,
        metadata,
        actions,
        "Review queue",
        "app.py:dashboard_page,apply_review_action",
        exit=(0, 0.5),
        entry=(1, 0.5),
    )
    d.text(
        "Retention: VM defaults to 30 days, detected-sensitive data to 7 days. Cloud lifecycle is configured separately.\nERP handoff is a placeholder; no ERP connector is deployed.",
        240,
        1200,
        1260,
        60,
        size=13,
    )

    d = a.page(
        "network",
        "OCI AI Document Review | Terraform network",
        "Source defaults, not a deployed inventory. Plain lines: associations. Arrows: configured routing. Dashed lines: access intent.",
    )
    internet = d.group("internet", "Trusted client network", 20, 280, 180, 270)
    client = d.icon(
        "User", 90, 140, parent=internet, label="Browser / SSH", label_pos="top"
    )
    region = d.group(
        "region",
        "OCI region: var.region | compartment: var.compartment_id",
        250,
        130,
        2030,
        1100,
    )
    vcn = a.resource(
        d.group(
            "vcn",
            "doc-review-vcn\n10.42.0.0/16 (default)",
            50,
            70,
            1300,
            930,
            parent=region,
        ),
        "oci_core_vcn.app",
    )
    public = a.resource(
        d.group(
            "subnet",
            "Public subnet\n10.42.1.0/24 (default)",
            140,
            120,
            430,
            270,
            parent=vcn,
        ),
        "oci_core_subnet.public",
    )
    vm = a.resource(
        d.icon(
            "Virtual Machine",
            210,
            140,
            parent=public,
            label="doc-review-app\nOracle Linux 9 | public IPv4",
            label_pos="bottom",
        ),
        "oci_core_instance.app",
    )
    private = a.resource(
        d.group(
            "subnet",
            "Private subnet\n10.42.2.0/24 (default)",
            730,
            120,
            500,
            270,
            parent=vcn,
        ),
        "oci_core_subnet.private",
    )
    function_app = a.resource(
        d.group(
            "other",
            "Functions application | optional",
            30,
            80,
            440,
            160,
            parent=private,
            style_extra="dashed=1;",
        ),
        "oci_functions_application.object_intake",
    )
    a.resource(
        d.icon(
            "OCI Functions",
            220,
            80,
            parent=function_app,
            label="Intake function\nenable_automatic_processing=true",
            label_pos="bottom",
        ),
        "oci_functions_function.object_intake",
    )
    igw = a.resource(
        d.icon(
            "Internet Gateway",
            0,
            220,
            parent=vcn,
            label="IGW",
            label_pos="top",
            border=True,
        ),
        "oci_core_internet_gateway.app",
    )
    pub_sl = a.resource(
        d.icon(
            "Security Lists",
            180,
            460,
            parent=vcn,
            label="Public security list\nTCP 22 / 8501: allowed CIDR",
            label_pos="bottom",
        ),
        "oci_core_security_list.public",
    )
    pub_rt = a.resource(
        d.icon(
            "Route Table",
            460,
            460,
            parent=vcn,
            label="Public route table",
            label_pos="bottom",
        ),
        "oci_core_route_table.public",
    )
    priv_sl = a.resource(
        d.icon(
            "Security Lists",
            790,
            460,
            parent=vcn,
            label="Private security list\nVCN TCP + ICMP; outbound allowed",
            label_pos="bottom",
        ),
        "oci_core_security_list.private",
    )
    priv_rt = a.resource(
        d.icon(
            "Route Table",
            1130,
            460,
            parent=vcn,
            label="Private route table",
            label_pos="bottom",
        ),
        "oci_core_route_table.private",
    )
    sgw = a.resource(
        d.icon(
            "Service Gateway",
            1300,
            640,
            parent=vcn,
            label="SGW",
            label_pos="top",
            border=True,
        ),
        "oci_core_service_gateway.app",
    )
    nat = a.resource(
        d.icon(
            "NAT Gateway",
            1300,
            830,
            parent=vcn,
            label="NAT Gateway",
            label_pos="top",
            border=True,
        ),
        "oci_core_nat_gateway.app",
    )
    osn = d.group("osn", "Oracle Services Network", 1550, 740, 420, 150, parent=region)
    d.text(
        "Regional services selected by\nAll .* Services In Oracle Services Network",
        20,
        45,
        380,
        70,
        parent=osn,
        size=13,
    )
    net = d.group("internet", "Public destinations", 2400, 960, 280, 140)
    a.resource(
        d.box(
            "Optional admin-group policy\nExisting group supplied by name\nObject operations + DU + GenAI\nHome-region IAM provider",
            1550,
            130,
            400,
            210,
            parent=region,
        ),
        "oci_identity_policy.admin_group",
    )
    identity_group = d.group(
        "other",
        "Runtime IAM | enable_instance_principal=true",
        1550,
        370,
        420,
        220,
        parent=region,
        style_extra="dashed=1;",
    )
    principal = a.resource(
        d.box("Dynamic group\nExact VM OCID", 20, 60, 170, 110, parent=identity_group),
        "oci_identity_dynamic_group.app_instance",
    )
    principal_policy = a.resource(
        d.box(
            "Runtime policy\nBucket + DU + GenAI\nProject compartment",
            230,
            60,
            170,
            110,
            parent=identity_group,
        ),
        "oci_identity_policy.app_instance",
    )
    a.edge(
        d,
        vm,
        principal,
        "Matches exact VM identity",
        "terraform/iam.tf:app_instance.matching_rule",
        kind="plain",
        exit=(0.5, 0),
        entry=(0, 0.5),
        waypoints=[(650, 260), (1690, 260), (1690, 615)],
    )
    a.edge(
        d,
        principal,
        principal_policy,
        "Policy subject",
        "terraform/iam.tf:app_instance.statements",
        kind="plain",
        exit=(1, 0.5),
        entry=(0, 0.5),
    )
    a.edge(
        d,
        client,
        igw,
        "Allowed ingress",
        "terraform/network.tf:public security list",
        kind="dashed",
        exit=(1, 0.5),
        entry=(0, 0.5),
    )
    a.edge(
        d,
        igw,
        vm,
        "22 / 8501",
        "terraform/network.tf:public; terraform/compute.tf:create_vnic_details",
        kind="dashed",
        exit=(1, 0.5),
        entry=(0, 0.5),
    )
    a.edge(
        d,
        public,
        pub_sl,
        "security_list_ids",
        "terraform/network.tf:public subnet",
        kind="plain",
        exit=(0.12, 1),
        entry=(0.5, 0),
    )
    a.edge(
        d,
        public,
        pub_rt,
        "route_table_id",
        "terraform/network.tf:public subnet",
        kind="plain",
        exit=(0.74, 1),
        entry=(0.5, 0),
    )
    a.edge(
        d,
        private,
        priv_sl,
        "security_list_ids",
        "terraform/network.tf:private subnet",
        kind="plain",
        exit=(0.12, 1),
        entry=(0.5, 0),
    )
    a.edge(
        d,
        private,
        priv_rt,
        "route_table_id",
        "terraform/network.tf:private subnet",
        kind="plain",
        exit=(0.8, 1),
        entry=(0.5, 0),
    )
    a.edge(
        d,
        pub_rt,
        igw,
        "0.0.0.0/0 → IGW",
        "terraform/network.tf:public route_rules",
        exit=(1, 0.5),
        entry=(1, 1),
        waypoints=[(900, 660), (900, 900), (370, 900), (370, 440)],
    )
    a.edge(
        d,
        priv_rt,
        sgw,
        "Regional OSN service CIDR",
        "terraform/network.tf:private service route",
        exit=(1, 0.5),
        entry=(0, 0.5),
        waypoints=[(1510, 660), (1510, 840)],
        label_offset=(-30, 0),
    )
    a.edge(
        d,
        priv_rt,
        nat,
        "0.0.0.0/0 → NAT",
        "terraform/network.tf:private default route",
        exit=(0, 0.5),
        entry=(0, 0.5),
        waypoints=[(1350, 660), (1350, 1030)],
    )
    a.edge(
        d,
        sgw,
        osn,
        "Service route",
        "terraform/network.tf:service_gateway.services",
        exit=(1, 0.5),
        entry=(0, 0.5),
    )
    a.edge(
        d,
        nat,
        net,
        "Private-subnet egress",
        "terraform/network.tf:private default route",
        exit=(1, 0.5),
        entry=(0, 0.5),
    )
    d.text(
        "VM traffic uses the PUBLIC route table (IGW), not the private subnet SGW/NAT routes.\nVM authentication defaults to an exact-instance Dynamic Group and scoped IAM policy. No NSG, load balancer, API Gateway or OIDC provider is created.",
        440,
        1320,
        2000,
        60,
        size=14,
    )

    d = a.page(
        "automation",
        "OCI AI Document Review | Optional automatic intake",
        "Enabled by enable_automatic_processing. Incoming objects and queue markers use distinct prefixes in the SAME private bucket.",
    )
    producer = d.icon("User", 90, 300, label="Trusted producer", label_pos="top")
    incoming = d.icon(
        "OCI Object Storage",
        400,
        300,
        label="Project bucket\nincoming/",
        label_pos="top",
    )
    events = a.resource(
        d.icon(
            "Events",
            700,
            300,
            label="OCI Events\nBucket create-object events",
            label_pos="top",
        ),
        "oci_events_rule.object_intake",
    )
    function = d.icon(
        "OCI Functions",
        1000,
        300,
        label="Intake function\nOnly incoming/ objects",
        label_pos="top",
    )
    queue = d.icon(
        "OCI Object Storage",
        1300,
        300,
        label="Same project bucket\nevent-queue/ JSON markers",
        label_pos="top",
    )
    poller = d.box(
        "VM systemd timer\npoll_event_queue.py\n60-second default interval",
        1180,
        600,
        260,
        120,
    )
    worker = d.box(
        "VM worker pool\nPreserve source; upload portal copy\nContinue document processing",
        750,
        600,
        260,
        120,
    )
    output = d.box(
        "Review queue\nJSON + report + human decision\nExternal incoming object retained",
        300,
        600,
        300,
        120,
    )
    group = a.resource(
        d.box(
            "Dynamic group\nExact intake function OCID\nResource principal",
            720,
            880,
            260,
            110,
        ),
        "oci_identity_dynamic_group.object_intake_function",
    )
    policy = a.resource(
        d.box(
            "Bucket-scoped IAM policy\nManage objects in project bucket\nHome-region IAM provider",
            1100,
            880,
            300,
            110,
        ),
        "oci_identity_policy.object_intake_function",
    )
    a.edge(
        d,
        producer,
        incoming,
        "Upload",
        "terraform/object_storage.tf:object_events_enabled",
        kind="dashed",
    )
    a.edge(
        d,
        incoming,
        events,
        "createobject",
        "terraform/events_functions.tf:object_intake.condition",
    )
    a.edge(
        d,
        events,
        function,
        "FAAS action",
        "terraform/events_functions.tf:object_intake.actions",
    )
    a.edge(
        d,
        function,
        queue,
        "Write queue marker",
        "functions/object_intake/func.py:handler",
    )
    a.edge(
        d,
        queue,
        poller,
        "Read markers + source",
        "src/event_intake.py:import_event_queue,import_marker",
        exit=(0.5, 1),
        entry=(0.46, 0),
    )
    a.edge(
        d,
        poller,
        worker,
        "Queue processing",
        "src/event_intake.py:import_marker",
        exit=(0, 0.5),
        entry=(1, 0.5),
    )
    a.edge(
        d,
        worker,
        output,
        "Analysis + review record",
        "src/processor.py:process",
        exit=(0, 0.5),
        entry=(1, 0.5),
    )
    a.edge(
        d,
        group,
        policy,
        "Policy subject",
        "terraform/events_functions.tf:object_intake_function policy",
        kind="plain",
    )
    a.edge(
        d,
        group,
        function,
        "Matches function OCID",
        "terraform/events_functions.tf:object_intake_function.matching_rule",
        kind="plain",
        exit=(0, 0.5),
        entry=(0.15, 1),
        waypoints=[(650, 935), (650, 390), (983, 390)],
    )
    a.edge(
        d,
        policy,
        queue,
        "Bucket object permissions",
        "terraform/events_functions.tf:object_intake_function.statements",
        kind="plain",
        exit=(1, 0.5),
        entry=(0.85, 1),
        waypoints=[(1560, 935), (1560, 390), (1317, 390)],
    )
    d.text(
        "Function application runs in the private subnet shown on the network page. Queue objects also generate bucket events; the function ignores objects outside incoming/.\nFunction image in OCIR and runtime OCI credentials/permissions are prerequisites. Intake downloads enforce MAX_UPLOAD_MB and the event ETag when provided.",
        240,
        1080,
        1450,
        70,
        size=13,
    )

    d = a.page(
        "case-assistant",
        "OCI AI Document Review | Optional ODA case assistant",
        "Read-only application integration. Dashed connectors require external ODA, OAuth, gateway, network and firewall configuration.",
    )
    user = d.icon("User", 90, 300, label="Authenticated ODA user", label_pos="top")
    oda = d.icon(
        "Digital Assistant",
        400,
        300,
        label="Oracle Digital Assistant\nSkill + OAuth account linking",
        label_pos="top",
    )
    gateway = d.icon(
        "API Gateway",
        750,
        300,
        label="Private API Gateway\nCustomer-managed prerequisite",
        label_pos="top",
    )
    runtime = d.group(
        "other",
        "Compute VM | CASE_CHAT_API_ENABLED=true",
        1020,
        170,
        430,
        720,
        style_extra="dashed=1;",
    )
    api = d.box(
        "FastAPI case-chat service\nOIDC token + exact case ACL\nPOST /v1/cases/{id}/chat",
        60,
        70,
        300,
        120,
        parent=runtime,
    )
    store = d.box(
        "Same-case evidence\nJSON analysis + review + comments\nRedacted restricted-case fields\nNo cross-document retrieval",
        60,
        430,
        300,
        150,
        parent=runtime,
    )
    genai = d.icon(
        "OCI Generative AI",
        1660,
        300,
        label="OCI Generative AI\nGrounded case answer",
        label_pos="top",
    )
    answer = d.box(
        "API response validation\nCited answer or safe refusal\nHuman review remains required\nNo approval / rejection endpoints",
        1510,
        610,
        340,
        150,
    )
    d.box(
        "Gateway backend prerequisites\nPrivate VM route + port 8081\nDefault listener is loopback only\nBind private IP and allow firewall access",
        570,
        500,
        370,
        160,
        kind="note",
    )
    d.text(
        "Default bind: 127.0.0.1:8081\nACL file must be supplied by the operator.",
        40,
        620,
        350,
        60,
        parent=runtime,
        size=12,
    )
    a.edge(
        d,
        user,
        oda,
        "Question + linked identity",
        "docs/oda_case_chat.md; oda/case-review-openapi.yaml",
        kind="dashed",
    )
    a.edge(d, oda, gateway, "Bearer token", "docs/oda_case_chat.md", kind="dashed")
    a.edge(
        d,
        gateway,
        api,
        "Private backend route :8081",
        "docs/oda_case_chat.md; ansible/playbook.yml:case-chat service",
        kind="dashed",
    )
    a.edge(
        d,
        api,
        store,
        "Authorized case only",
        "src/case_chat_api.py:chat_about_case",
        exit=(0.5, 1),
        entry=(0.5, 0),
    )
    a.edge(
        d,
        api,
        genai,
        "Evidence + question",
        "src/case_chat_api.py:chat_about_case; src/genai_client.py:answer_case_question",
    )
    a.edge(
        d,
        genai,
        answer,
        "Answer validated by API",
        "src/case_chat_api.py:chat_about_case",
        exit=(0.5, 1),
        entry=(0.44, 0),
    )
    d.text(
        "ODA, API Gateway and the OIDC provider are NOT created by the project's Terraform.\nThe Streamlit case-chat widget is a separate local demonstration; the portal itself has no built-in user authentication.",
        300,
        1020,
        1600,
        70,
        size=14,
    )
    a.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=Path(
            os.getenv(
                "OCI_DIAGRAM_SKILL",
                Path.home() / ".codex/skills/oci-architecture-diagrams",
            )
        ),
    )
    args = parser.parse_args()
    build(args.skill_dir)


if __name__ == "__main__":
    main()

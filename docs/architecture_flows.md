# Architecture Flows

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.3.0`

## End-to-End MVP Flow

Rendered share-ready diagram:

![OCI AI Document Review architecture](assets/oci-ai-document-review-architecture.png)

Editable source:

```text
docs/assets/oci-ai-document-review-architecture.excalidraw
docs/assets/oci-ai-document-review-architecture.svg
```

```text
+---------------+
| Business User |
+-------+-------+
        |
        v
+--------------------------+
| Streamlit Web Portal     |
| Upload / Dashboard /     |
| Actions / Settings       |
+------------+-------------+
             |
             v
+--------------------------+
| Local Working Copy       |
| Download + Retry         |
+------------+-------------+
             |
             v
+--------------------------+
| Background Worker Pool   |
| Queue, Parallel Jobs     |
+------------+-------------+
             |
             v
+--------------------------+
| OCI Object Storage       |
| Private Original Files   |
+------------+-------------+
             |
             +---------------------------+----------------------------+
             |                                                        |
             | text files / PDFs with selectable text                  | images / scanned PDFs
             v                                                        v
+--------------------------+                    +----------------------------+
| Local Text Extraction    |                    | OCI Document Understanding |
| No DU Call               |                    | OCR + Rich Extraction      |
+------------+-------------+                    +-------------+--------------+
             |                                                |
             |                                                v
             |                                  +----------------------------+
             |                                  | DU Text-Only OCR Fallback  |
             |                                  | When Rich Extraction Fails |
             |                                  +-------------+--------------+
             |                                                |
             +---------------------------+--------------------+
                                         |
                                         v
                    +----------------------------+
                    | OCI Generative AI          |
                    | Type, Summary, Fields,     |
                    | Risks, Recommendations     |
                    +-------------+--------------+
                                  |
                                  | content safety block
                                  v
                    +----------------------------+
                    | Safety Message Sanitizer   |
                    | Manual Review Fallback     |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | Compliance Risk Overlay    |
                    | Public-Sector Expense Flag |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | Local JSON Metadata        |
                    | Report, Workflow, Audit    |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | Dashboard Queue            |
                    | URL State + Fragment       |
                    | Refresh + Split Tables     |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | Actions Review             |
                    | Source Download, Workflow  |
                    | Type, Decide               |
                    | Next-In-Line Routing       |
                    +----------------------------+
```

## Deployed Runtime Flow

```text
+-------------------------+
| User Browser            |
+-----------+-------------+
            |
            | HTTP :8501
            v
+-------------------------+
| OCI Compute VM          |
| Streamlit + Worker Pool |
+-----------+-------------+
            |
            +--> Source Download
            |    Download Doc for Review from data/uploads
            |
            +--> Local Text Extract
            |    Text files / PDFs with selectable text
            |
            +--> OCI SDK using API key and IAM policies
                 |
                 +--> Object Storage
                 |    Uploaded originals
                 |
                 +--> Document Understanding OCR
                 |    Images / scanned PDFs
                 |
                 +--> DU text-only OCR fallback
                 |    Used when table/key-value extraction fails
                 |
                 +--> Generative AI
                 |    Structured review
                 |
                 +--> Safety sanitizer
                 |    Manual-review fallback and raw provider JSON scrub
                 |
                 +--> Compliance risk overlay
                 |    Public-sector expense attention flag
                 |
                 +--> Local JSON metadata
                      Reports, workflow, audit, retries, source download path
```

## Processing Sequence

```text
+----------------------+
| Streamlit Upload     |
+----------+-----------+
           |
           v
+----------------------+
| Local Working Copy   |
| data/uploads         |
+----------+-----------+
           |
           | metadata status UPLOADED
           v
+----------------------+
| Worker Pool          |
| MAX_PARALLEL_JOBS    |
+----------+-----------+
           |
           | each active worker runs the extraction and GenAI path
           v
+----------------------+
| Active Worker        |
+----------+-----------+
           |
           | put_object
           v
+----------------------+
| Object Storage       |
| Private Bucket       |
+----------+-----------+
           |
           +-----------------------------+
           |                             |
           | text-native / text PDFs     | images / scanned PDFs
           v                             v
+----------------------+     +----------------------------+
| Local Text Extract   |     | Document Understanding     |
| TXT / CSV / PDF text |     | OCR, Tables, Key Values    |
+----------+-----------+     +----------+-----------------+
           |                             |
           |                             v
           |                  +----------------------------+
           |                  | Text-Only OCR Fallback     |
           |                  | If Rich Extraction Fails   |
           |                  +----------+-----------------+
           |                             |
           +-------------+---------------+
                         |
                         | extracted content
                         v
+----------------------------+
| Generative AI              |
| CohereChatRequest          |
+----------+-----------------+
           |
           +-----------------------------+
           |                             |
           | strict JSON analysis        | content safety block
           v                             v
+----------------------------+
| Type Label                 |
| Auto-detect -> Real Type   |
+----------+-----------------+
           |                  +----------------------------+
           |                  | Safety Message Sanitizer   |
           |                  | Fallback Analysis          |
           |                  +-------------+--------------+
           |                                |
           +----------------+---------------+
                            |
                            v
              +----------------------------+
              | Sanitized Analysis         |
              | No Raw Provider JSON       |
              +-------------+--------------+
                            |
                            v
              +----------------------------+
              | Compliance Overlay         |
              | Object Storage KB Match    |
              | Public-Sector Expense Risk |
              +----------+-----------------+
                         |
                         v
              +----------------------------+
              | Metadata + Report          |
              | JSON + Markdown + Audit    |
              +----------+-----------------+
                         |
                         v
              +----------------------------+
              | Dashboard Queue            |
              | Processing / Ready /       |
              | Failed / Reviewed          |
              +----------+-----------------+
                         |
                         v
              +----------------------------+
              | Actions Review             |
              | Source Download / Workflow |
              | Type / Approve             |
              | Next-In-Line Navigation    |
              +----------------------------+
```

## Safety Filter Flow

```text
+--------------------------+
| OCI Generative AI Call   |
+------------+-------------+
             |
             +----------------------------+----------------------------+
             |                            |                            |
             v                            v                            |
+--------------------------+  +----------------------------+           |
| Structured JSON Analysis |  | Provider Content Block     |           |
| Normal Review Path       |  | InvalidParameter / Safety  |           |
+------------+-------------+  +-------------+--------------+           |
             |                              |                          |
             |                              v                          |
             |                 +----------------------------+          |
             |                 | src/safety_messages.py     |          |
             |                 | Sanitized Reviewer Message |          |
             |                 +-------------+--------------+          |
             |                               |                         |
             |                               v                         |
             |                 +----------------------------+          |
             |                 | Fallback Analysis          |          |
             |                 | Risk High + Manual Review  |          |
             |                 +-------------+--------------+          |
             |                               |                         |
             +---------------+---------------+                         |
                             |                                         |
                             v                                         |
              +----------------------------+                           |
              | Metadata / UI / Downloads  |                           |
              | No Raw Provider JSON       |                           |
              +----------------------------+                           |
```

## Source Download Flow

```text
+--------------------------+
| Uploaded File            |
+------------+-------------+
             |
             v
+--------------------------+
| Local Working Copy       |
| data/uploads             |
+------------+-------------+
             |
             v
+--------------------------+
| Actions Source Document  |
| Download Doc for Review  |
+------------+-------------+
             |
             v
+--------------------------+
| Approver Opens File      |
| Locally For Review       |
+--------------------------+
```

## Document Lifecycle Workflow

```text
+--------------------------+
| Dashboard Next Action    |
| Processing / Ready / ... |
+------------+-------------+
             |
             v
+--------------------------+
| Actions Page             |
| Source Download          |
| Decision + Workflow      |
+------------+-------------+
             |
             +----------------------+----------------------+-------------------+
             |                      |                      |                   |
             v                      v                      v                   v
+-------------------+  +---------------------+  +-------------------+  +-------------------+
| Assign Owner      |  | Set SLA Due Date    |  | Add Comment      |  | Retry Failure     |
| Workflow Status   |  | Overdue/Due Today   |  | Reviewer Notes   |  | Child Run Queued  |
+---------+---------+  +----------+----------+  +---------+---------+  +---------+---------+
          |                       |                       |                      |
          +-----------+-----------+-----------+-----------+----------+-----------+
                                              |
                                              v
                               +----------------------------+
                               | Local JSON Metadata        |
                               | workflow_comments          |
                               | audit_events               |
                               | retry_history              |
                               +-------------+--------------+
                                             |
                                             v
                               +----------------------------+
                               | Markdown / JSON Downloads  |
                               | Updated From Latest State  |
                               +----------------------------+
```

## Dashboard Refresh Flow

```text
+----------------------+
| Browser On Dashboard |
+----------+-----------+
           |
           | ?page=Dashboard keeps route stable on browser refresh
           v
+----------------------+
| Static Page Shell    |
| Header + Sidebar     |
+----------+-----------+
           |
           | Streamlit fragment reruns every 10 seconds
           v
+----------------------+
| Dashboard Components |
| Metrics, Next Action,|
| Search, Split Tables |
+----------+-----------+
           |
           | reads latest local JSON metadata
           v
+----------------------+
| Updated Queue State  |
| Processing -> Ready  |
| Failed -> Retry      |
+----------------------+
```

## Preflight Flow

```text
+----------------------+
| Settings Page        |
| Run OCI Preflight    |
+----------+-----------+
           |
           +--------------------+----------------------+--------------------+
           |                    |                      |                    |
           v                    v                      v                    |
+-------------------+  +---------------------+  +-------------------+     |
| Object Storage    |  | Document             |  | Generative AI     |     |
| write/read/delete |  | Understanding API    |  | model response    |     |
+-------------------+  +---------------------+  +-------------------+     |
           |                    |                      |                    |
           +--------------------+----------------------+--------------------+
                                |
                                v
                     +----------------------+
                     | Pass / Fail Results  |
                     +----------------------+
```

## Extraction Decision Flow

```text
+----------------------+
| Uploaded File        |
+----------+-----------+
           |
           v
+----------------------+
| File Extension       |
| and PDF Text Probe   |
+----------+-----------+
           |
           +------------------------------+------------------------------+
           |                              |                              |
           v                              v                              v
+----------------------+      +----------------------+      +----------------------+
| Text-Native File     |      | PDF With Text        |      | Image / Image PDF    |
| TXT, CSV, JSON, ...  |      | Selectable Content   |      | PNG, JPG, Scan       |
+----------+-----------+      +----------+-----------+      +----------+-----------+
           |                             |                             |
           v                             v                             v
+----------------------+      +----------------------+      +----------------------+
| Local Text Read      |      | Local PDF Text Read  |      | OCI Document         |
| No DU Call           |      | No DU Call           |      | Understanding OCR    |
+----------+-----------+      +----------+-----------+      +----------+-----------+
           |                             |                             |
           |                             |                             v
           |                             |                  +----------------------+
           |                             |                  | Text-Only OCR        |
           |                             |                  | Fallback if Needed   |
           |                             |                  +----------+-----------+
           |                             |                             |
           +-------------+---------------+---------------+-------------+
                         |
                         v
              +----------------------+
              | OCI Generative AI    |
              | Structured Review    |
              +----------------------+
                         |
                         v
              +----------------------+
              | Compliance Overlay   |
              | Object Storage KB    |
              | Compliance Review    |
              +----------------------+
```

## OCI Network Flow

```text
+---------------------------------------------------------------+
| Project Compartment                                           |
|                                                               |
|  +---------------------------------------------------------+  |
|  | VCN 10.42.0.0/16                                       |  |
|  |                                                         |  |
|  |  +---------------------+       +---------------------+  |  |
|  |  | Public Subnet       |       | Private Subnet      |  |  |
|  |  | 10.42.1.0/24        |       | 10.42.2.0/24        |  |  |
|  |  |                     |       |                     |  |  |
|  |  | Streamlit VM        |       | Future services     |  |  |
|  |  | Public IP: yes      |       | Public IP: no       |  |  |
|  |  | Ports: 22, 8501     |       | VCN traffic only    |  |  |
|  |  +----------+----------+       +----------+----------+  |  |
|  |             |                             |             |  |
|  |             v                             v             |  |
|  |  +---------------------+       +---------------------+  |  |
|  |  | Public Route Table  |       | Private Route Table |  |  |
|  |  | 0.0.0.0/0 -> IGW    |       | OSN -> SGW          |  |  |
|  |  +----------+----------+       | 0.0.0.0/0 -> NAT GW |  |  |
|  |             |                  +----------+----------+  |  |
|  |             v                             |             |  |
|  |  +---------------------+                  |             |  |
|  |  | Internet Gateway    |                  |             |  |
|  |  +---------------------+                  |             |  |
|  |                                           |             |  |
|  |  +---------------------+       +----------v----------+  |  |
|  |  | Public Security     |       | NAT Gateway         |  |  |
|  |  | List                |       +---------------------+  |  |
|  |  | Allow 22 and 8501   |                              |  |
|  |  | from allowed CIDR   |       +---------------------+  |  |
|  |  +---------------------+       | Service Gateway     |  |  |
|  |                                +---------------------+  |  |
|  |  No NSGs are created.                                  |  |
|  +---------------------------------------------------------+  |
+---------------------------------------------------------------+
```

## Terraform and Ansible Flow

```text
+---------------------+
| Local Workstation   |
+----------+----------+
           |
           v
+---------------------+
| Terraform           |
| OCI Infrastructure  |
+----------+----------+
           |
           +-------------------+-------------------+-------------------+
           |                   |                   |                   |
           v                   v                   v                   v
+----------------+  +----------------+  +----------------+  +----------------+
| Compartment    |  | VCN / Subnet    |  | Compute VM     |  | Object Storage |
+----------------+  +----------------+  +----------------+  +----------------+
                                           |
                                           v
                                +---------------------+
                                | Ansible             |
                                | App Release + Config|
                                +----------+----------+
                                           |
                                           v
                                +---------------------+
                                | systemd Streamlit   |
                                | Running Portal      |
                                +---------------------+
```

## Release Hygiene Flow

```text
+---------------------+
| Local Repository    |
+----------+----------+
           |
           | tar excludes .git, caches,
           | secrets, state, and data
           v
+---------------------+
| Release Archive     |
| App Code Only       |
+----------+----------+
           |
           | Ansible unarchive
           v
+---------------------+
| VM App Directory    |
| Scrub Local Files   |
+----------+----------+
           |
           | Write runtime config
           v
+---------------------+
| Expected Runtime    |
| .env + .oci/config  |
+---------------------+
```

## Configuration Boundary Flow

```text
+----------------------------+
| Tracked Repository         |
| code, docs, lock files     |
+-------------+--------------+
              |
              | deploy script reads local runtime values
              v
+----------------------------+       +----------------------------+
| Local-Only Files           |       | OCI VM Runtime             |
| .env, tfvars, state, keys  | ----> | .env, .oci/config, key     |
+----------------------------+       +-------------+--------------+
                                                   |
                                                   v
                                      +----------------------------+
                                      | Streamlit + Worker Pool    |
                                      | Object Storage / DU / GenAI|
                                      | Compliance KB Overlay      |
                                      +----------------------------+
```

## Phase 2 Enterprise Flow

```text
+---------------+
| Business User |
+-------+-------+
        |
        v
+-------------------------+
| APEX / Visual Builder   |
| or Streamlit            |
+-------+-----------------+
        |
        v
+-------------------------+
| Backend Processor       |
| Python / API            |
+-------+-----------------+
        |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
+-------------------+  +---------------------+  +-------------------+
| Object Storage    |  | Document             |  | Generative AI     |
| Original Files    |  | Understanding        |  | Analysis          |
+-------------------+  +---------------------+  +-------------------+
        |                      |                      |
        +----------------------+----------------------+
                               |
                               v
                    +-----------------------+
                    | Autonomous Database   |
                    | Metadata and Review   |
                    +-----------------------+
```

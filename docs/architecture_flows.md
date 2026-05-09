# Architecture Flows

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.5.0`

## End-to-End MVP Flow

Rendered share-ready diagram:

![OCI AI Document Review architecture](../Architecture.png)

Editable source:

```text
docs/assets/oci-ai-document-review-architecture.excalidraw
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
| 1-5 Files Per Submission |
+------------+-------------+
             |
             v
+--------------------------+
| Local Working Copy       |
| Expense Name / Ref       |
| Metadata                 |
| Download + Retry         |
| 30-Day Default Retention |
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
| documents/ Retention     |
+------------+-------------+
             |
             +---------------------------+----------------------------+
             |                                                        |
             | text files / PDFs with selectable text                  | images / scanned PDFs
             v                                                        v
+--------------------------+                    +----------------------------+
| Local Text Extraction    |                    | OCI Document Understanding |
| No DU Call               |                    | OCR + Rich Extraction      |
|                          |                    | Limit-Safe PDF Chunks      |
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
                    | Compact Groups + Filters   |
                    | Elapsed + Stale Refresh    |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | Actions Review             |
                    | Decision First             |
                    | Linked Files + Source      |
                    | Download, Workflow         |
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
                 |    Scanned PDFs split into limit-safe chunks when needed
                 |    Chunk names keep original stem: file_1.pdf, file_2.pdf
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
| Expense Name / Ref   |
+----------+-----------+
           |
           | one metadata record per file
           | shared expense/reference for multi-file submissions
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
|                      |     | Limit-Safe PDF Chunking    |
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
              | Compact Groups / Filters   |
              | Processing / Ready /       |
              | Failed / Reviewed          |
              | Active Elapsed + Stale Fix |
              +----------+-----------------+
                         |
                         v
              +----------------------------+
              | Actions Review             |
              | Decision First             |
              | Linked Files / Source      |
              | Download / Workflow        |
              | Next-In-Line Navigation    |
              +----------------------------+
```

## Upload Batch and Expense Group Flow

```text
+--------------------------+
| Upload Page              |
| Select 1 to 5 files      |
+------------+-------------+
             |
             +----------------------------+----------------------------+
             |                            |                            |
             v                            v                            |
+--------------------------+  +----------------------------+           |
| Single File              |  | Multiple Files             |           |
| Expense Name / Ref       |  | Expense Name / Ref Needed  |           |
| Optional                 |  | Before Queueing            |           |
+------------+-------------+  +-------------+--------------+           |
             |                              |                          |
             +---------------+--------------+                          |
                             |                                         |
                             v                                         |
              +----------------------------+                           |
              | One Metadata Record        |                           |
              | Per Uploaded File          |                           |
              +-------------+--------------+                           |
                            |
                            v
              +----------------------------+
              | Shared Expense Name / Ref  |
              | Stored On Each File        |
              +-------------+--------------+
                            |
                            v
              +----------------------------+
              | Dashboard Expense Groups   |
              | Overview + Compact Cards   |
              | One Review Button          |
              | Collapsed Show Files       |
              +-------------+--------------+
                            |
                            v
              +----------------------------+
              | Actions Linked Files Panel |
              | Decision Panel At Top      |
              | Group Item Aggregation     |
              | End-To-End Batch Context   |
              +----------------------------+
```

## Compact Dashboard Review Flow

```text
+----------------------------+
| Dashboard Phase Queue      |
| Processing / Ready / ...   |
+-------------+--------------+
              |
              +----------------------------+----------------------------+
              |                            |                            |
              v                            v                            |
+----------------------------+  +----------------------------+          |
| Selectable File Table      |  | Multi-File Expense Group   |          |
| Review Selected Button     |  | Compact Summary Card       |          |
+-------------+--------------+  +-------------+--------------+          |
              |                               |                         |
              |                               v                         |
              |                 +----------------------------+          |
              |                 | Review Button              |          |
              |                 | Best Next Actionable File  |          |
              |                 +-------------+--------------+          |
              |                               |                         |
              |                               v                         |
              |                 +----------------------------+          |
              |                 | Show Files Expander        |          |
              |                 | Collapsed By Default       |          |
              |                 +-------------+--------------+          |
              |                               |                         |
              +---------------+---------------+                         |
                              |                                         |
                              v                                         |
                +----------------------------+                          |
                | Actions Page               |                          |
                | Decision Panel Near Top    |                          |
                | Approve / Reject / Type    |                          |
                +----------------------------+                          |
```

## OCI Events And Functions Intake Flow

```text
+-----------------------------+
| Local setup / Terraform     |
| tenancy_id + OCIR image     |
| automatic processing gate   |
+--------------+--------------+
               |
               v
+-----------------------------+
| External System / Customer  |
| uploads to incoming/        |
+--------------+--------------+
               |
               v
+-----------------------------+
| OCI Object Storage          |
| Private Bucket              |
| object events enabled       |
+--------------+--------------+
               |
               v
+-----------------------------+
| OCI Events Rule             |
| Object Create In Bucket     |
+--------------+--------------+
               |
               v
+-----------------------------+
| OCI Function                |
| functions/object_intake     |
| filters incoming/ prefix    |
+--------------+--------------+
               |
               v
+-----------------------------+
| event-queue/*.json marker   |
| bucket, object, event id    |
+--------------+--------------+
               |
               v
+-----------------------------+
| VM systemd timer            |
| poll_event_queue.py         |
+--------------+--------------+
               |
               v
+-----------------------------+
| Existing Worker Queue       |
| DU / GenAI / Compliance     |
+--------------+--------------+
               |
               v
+-----------------------------+
| Dashboard + Actions         |
| Human Approval Workflow     |
+-----------------------------+
```

## Dashboard Filter Flow

```text
+---------------------------+
| Dashboard Work Queues     |
| Search + Status Filter    |
| Compact Expense Groups    |
+-------------+-------------+
              |
              v
+---------------------------+
| Queue Row Metadata        |
| status, review, action,   |
| workflow, SLA, risk,      |
| expense/reference         |
+-------------+-------------+
              |
              +-----------------------+-----------------------+-----------------------+
              |                       |                       |                       |
              v                       v                       v                       v
+---------------------+   +---------------------+   +---------------------+   +---------------------+
| Processing Filter   |   | Decision Filter     |   | Follow-Up Filter    |   | Reviewed Filter     |
| active statuses     |   | needs/compliance    |   | failed/retry        |   | approved/rejected   |
+----------+----------+   +----------+----------+   +----------+----------+   +----------+----------+
           |                         |                         |                         |
           +-------------------------+-------------------------+-------------------------+
                                     |
                                     v
                         +---------------------------+
                         | Visible Queue Sections    |
                         | Processing / Ready /      |
                         | Failed / Reviewed         |
                         | Compact Review Groups     |
                         +---------------------------+
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
| Decision First           |
| Source Download + Flow   |
+------------+-------------+
             |
             +------------------+------------------+------------------+------------------+
             |                  |                  |                  |                  |
             v                  v                  v                  v                  v
+----------------+  +----------------+  +----------------+  +----------------+  +----------------+
| Approve/Reject |  | Assign Owner   |  | Set SLA Date   |  | Add Comment    |  | Retry Failure  |
| Human Decision |  | Workflow State |  | Due Tracking   |  | Reviewer Notes |  | Child Queued   |
+-------+--------+  +-------+--------+  +-------+--------+  +-------+--------+  +-------+--------+
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
| Search, Filters,     |
| Groups, Split Tables |
+----------+-----------+
           |
           | reads latest local JSON metadata
           | marks stale active records failed
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
|                      |      |                      |      | Limit-Safe Chunks    |
|                      |      |                      |      | OriginalStem_N.pdf   |
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
| IAM Policies   |  | Function App    |  | RETENTION_DAYS |  | Events Enabled |
+----------------+  +----------------+  +----------------+  +----------------+
                                           |
                                           v
                                +---------------------+
                                | Ansible             |
                                | App Release + Timers|
                                +----------+----------+
                                           |
                                           v
                                +---------------------+
                                | systemd Streamlit   |
                                | Running Portal      |
                                +---------------------+
```

## Retention Flow

```text
+-------------------------+
| scripts/setup.py        |
| asks retention days     |
| default: 30             |
+------------+------------+
             |
             +----------------------------+
             |                            |
             v                            v
+-------------------------+     +--------------------------+
| .env                    |     | terraform.tfvars         |
| RETENTION_DAYS=30       |     | retention_days = 30      |
+------------+------------+     +------------+-------------+
             |                               |
             v                               v
+-------------------------+     +--------------------------+
| Streamlit VM            |     | OCI Object Storage       |
| app cleanup plus daily  |     | lifecycle deletes only   |
| systemd timer           |     | documents/ objects       |
+------------+------------+     +------------+-------------+
             |                               |
             v                               v
+-------------------------+     +--------------------------+
| Active processing       |     | compliance/ KB remains   |
| records are protected   |     | outside lifecycle rule   |
+-------------------------+     +--------------------------+
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
        +---------------------------+
        |                           |
        v                           v
+-------------------------+   +-------------------------+
| Review UI               |   | Customer Chatbot        |
| Upload / Dashboard /    |   | Status, rejection, SLA, |
| Actions                 |   | retry, risk questions   |
+-------+-----------------+   +------------+------------+
        |                                  |
        +----------------------+-----------+
                               |
        v
+-------------------------+
| Backend Processor       |
| Python / API            |
+-------+-----------------+
        |
        +----------------------+----------------------+----------------------+
        |                      |                      |                      |
        v                      v                      v                      v
+-------------------+  +---------------------+  +-------------------+  +-----------------------+
| Object Storage    |  | Document             |  | Generative AI     |  | Autonomous Database   |
| Original Files    |  | Understanding        |  | Analysis + Chat   |  | Metadata, Review, ACL |
+-------------------+  +---------------------+  +-------------------+  +-----------------------+
```

The Phase 2 chatbot should be read-only and grounded in stored metadata, audit events, workflow comments, extracted summaries, generated reports, and review decisions. It should answer customer questions about status, rejection reason, retry instructions, owner, SLA, and risk summaries, while enforcing document-level authorization.

## Phase 2 Customer Chatbot Flow

```text
+---------------------------+
| Customer                  |
| "What is my file status?" |
+-------------+-------------+
              |
              v
+---------------------------+
| Authenticated Chat UI     |
| customer/session context  |
+-------------+-------------+
              |
              v
+---------------------------+
| Document Access Filter    |
| customer, tenant, case id |
+-------------+-------------+
              |
              v
+---------------------------+
| Retrieval                 |
| metadata, audit events,   |
| comments, reports,        |
| extracted summaries       |
+-------------+-------------+
              |
              v
+---------------------------+
| OCI Generative AI         |
| grounded answer only      |
+-------------+-------------+
              |
              v
+---------------------------+
| Customer Answer           |
| status, rejection reason, |
| owner, SLA, retry step    |
+---------------------------+
```

# Architecture Flows

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

## End-to-End MVP Flow

Rendered share-ready diagram:

![OCI AI Document Review architecture](assets/oci-ai-document-review-architecture.png)

Editable source:

```text
docs/assets/oci-ai-document-review-architecture.svg
```

```text
+---------------+
| Business User |
+-------+-------+
        |
        v
+-----------------------+
| Streamlit Web Portal  |
+-------+---------------+
        |
        v
+-----------------------+
| Upload Document       |
+-------+---------------+
        |
        v
+-----------------------+
| Background Worker     |
| Queue, Parallel Jobs  |
+-------+---------------+
        |
        v
+-----------------------+
| OCI Object Storage    |
| Private Bucket        |
+-------+---------------+
        |
        v
+----------------------------+
| Local Text or OCI Document |
| Understanding Extraction   |
+-------+--------------------+
        |
        v
+-----------------------+
| OCI Generative AI     |
| Type, Summary, Risks  |
+-------+---------------+
        |
        v
+----------------------------+
| Local JSON Metadata        |
| Report, Workflow, Audit    |
+------------+---------------+
        |
        v
+-----------------------+
| Dashboard Queue       |
| Next Action + Tables  |
+-------+---------------+
        |
        v
+-----------------------+
| Actions Review        |
| Type, Workflow, Decide|
+-----------------------+
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
            +--> Local Text Extract
            |    Text files / PDFs with selectable text
            |
            +--> OCI SDK using API key and IAM policies
                 |
                 +--> Object Storage
                 |    Uploaded originals
                 |
                 +--> Document Understanding OCR
                 |    Images / image-only PDFs
                 |
                 +--> Generative AI
                 |    Structured review
                 |
                 +--> Local JSON metadata
                      Reports, workflow, audit, retries
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
           | text-native / text PDFs     | images / image-only PDFs
           v                             v
+----------------------+     +----------------------------+
| Local Text Extract   |     | Document Understanding     |
| TXT / CSV / PDF text |     | Text, Tables, Key Values   |
+----------+-----------+     +----------+-----------------+
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
           | strict JSON analysis
           v
+----------------------------+
| Type Label                 |
| Auto-detect -> Real Type   |
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
| Ready / Failed / Reviewed  |
+----------+-----------------+
           |
           v
+----------------------------+
| Actions Review             |
| Workflow / Type / Approve  |
+----------------------------+
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
           +-------------+---------------+---------------+-------------+
                         |
                         v
              +----------------------+
              | OCI Generative AI    |
              | Structured Review    |
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

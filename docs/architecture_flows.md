# Architecture Flows

## End-to-End MVP Flow

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
| Upload PDF / Image    |
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
| OCI Document Understanding |
| Text, Tables, Fields       |
+-------+--------------------+
        |
        v
+-----------------------+
| OCI Generative AI     |
| Summary, Risks, JSON  |
+-------+---------------+
        |
        v
+-----------------------+
| Review Dashboard      |
| Approve / Reject      |
+-------+---------------+
        |
        v
+-----------------------+
| Markdown / JSON Report|
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
| Streamlit + Python      |
+-----------+-------------+
            |
            | OCI SDK
            v
+-------------------------+
| Existing OCI API Key    |
| Existing IAM Policies   |
+-----------+-------------+
            |
            +--------------------+--------------------+
            |                    |                    |
            v                    v                    v
+-------------------+  +---------------------+  +-------------------+
| Object Storage    |  | Document             |  | Generative AI     |
| Uploaded Files    |  | Understanding        |  | Selected Region   |
+-------------------+  +---------------------+  +-------------------+
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
           | put_object
           v
+----------------------+
| Object Storage       |
| Private Bucket       |
+----------+-----------+
           |
           | ObjectStorageDocumentDetails
           v
+----------------------------+
| Document Understanding     |
| Text, Tables, Key Values   |
+----------+-----------------+
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
| Metadata + Report          |
| JSON + Markdown            |
+----------+-----------------+
           |
           v
+----------------------------+
| Review Dashboard           |
| Human Approve / Reject     |
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
           | tar excludes local-only files
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

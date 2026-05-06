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
| Uploaded Files    |  | Understanding        |  | London Region     |
+-------------------+  +---------------------+  +-------------------+
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
                                | App Configuration   |
                                +----------+----------+
                                           |
                                           v
                                +---------------------+
                                | systemd Streamlit   |
                                | Running Portal      |
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

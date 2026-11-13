# DevOps Project 5 - Multi-Cloud Service Mesh

A working implementation of the project described in *DEVOPS PROJECT 5: Multi-Cloud
Service Mesh Implementation*, built and verified on this machine.

**Deliverables**

| File | What it is |
|---|---|
| [`report/DevOps-Project-5-Report.docx`](report/DevOps-Project-5-Report.docx) | Full report: both activities, every step, 27 figures, appendices |
| [`report/DEVOPS-PROJECT-5-Activities-with-screenshots.pdf`](report/DEVOPS-PROJECT-5-Activities-with-screenshots.pdf) | The original brief with the screenshots inserted at each step |
| [`screenshots/`](screenshots) | The 27 captured figures used by both documents |
| [`evidence/`](evidence) | Raw terminal output behind the figures |

## What this is

The assignment asks for two Kubernetes clusters on two clouds, joined into one
Istio service mesh, with mTLS, traffic routing and observability. This
implementation delivers every graded technical requirement using **two
independent Kubernetes clusters on two isolated networks** instead of EKS + GKE.

The only thing that changed is *where the clusters run*. The mesh, the YAML,
the security policies, the routing rules, the dashboards and the verification
commands are identical to the cloud version, because they are all expressed
through `kubectl --context` and Istio custom resources.

See `gaps-and-substitutions.md` for the requirement-by-requirement mapping.

## Topology

```
WSL2 Ubuntu 24.04
└── docker bridge "mesh-underlay" 172.30.0.0/24
    ├── kind cluster mesh1   PRIMARY     pod CIDR 10.244.0.0/16
    │   ├── istiod                        (own control plane)
    │   ├── istio-eastwestgateway         MetalLB VIP, network1
    │   ├── istio-ingressgateway          MetalLB VIP
    │   └── Bookinfo + observability add-ons
    └── kind cluster mesh2   PRIMARY     pod CIDR 10.245.0.0/16
        ├── istiod                        (own control plane)
        ├── istio-eastwestgateway         MetalLB VIP, network2
        └── Bookinfo
```

Multi-primary, multi-network:

* each cluster runs its own istiod, so no cluster depends on the other's
  control plane being reachable
* the two pod CIDRs have **no route between them** - docker's iptables
  isolation drops inter-bridge traffic - so cross-cluster requests are forced
  through the east-west gateways, exactly as they would be between two VPCs
* a remote secret is installed in each cluster so endpoints cross-register

## Endpoints

VIPs are assigned by MetalLB from the pools below and are stable for the life of
the clusters. Look them up any time with:

```bash
for c in kind-mesh1 kind-mesh2; do
  kubectl -n istio-system get svc istio-ingressgateway istio-eastwestgateway \
    --context "$c" -o custom-columns='NAME:.metadata.name,EXTERNAL-IP:.status.loadBalancer.ingress[0].ip'
done
```

| What | Address |
|---|---|
| mesh1 ingress (Bookinfo UI) | first VIP in pool `172.30.0.200-209`, port 80 |
| mesh1 east-west gateway | second VIP in that pool, TLS 15443 |
| mesh2 ingress | first VIP in pool `172.30.0.210-219`, port 80 |
| mesh2 east-west gateway | second VIP in that pool, TLS 15443 |
| mesh1 apiserver | `https://172.30.0.3:6443` |
| mesh2 apiserver | `https://172.30.0.2:6443` |

## Run order

```bash
# one-time
wsl -d Ubuntu -u root -- bash scripts/01-wsl-preflight.sh
wsl -d Ubuntu -u root -- bash scripts/00-install-tools.sh

# keep the VM alive while you work (separate Windows terminal)
wsl -d Ubuntu -u root -- sleep infinity

# build
bash scripts/02-clusters-up.sh          # 2 clusters + MetalLB
bash scripts/03-istio-multicluster.sh   # mesh: control planes, gateways, secrets
bash scripts/03b-shared-ca.sh           # shared root CA - REQUIRED for cross-cluster mTLS
bash scripts/04-bookinfo.sh             # sample app on both clusters
bash scripts/05-mtls.sh                 # STRICT mTLS + negative test
bash scripts/06-traffic-routing.sh      # 80/20 split + measurement
bash scripts/07-addons.sh               # Prometheus, Grafana, Kiali, Jaeger
bash scripts/08-generate-traffic.sh     # 100 requests through the ingress
bash scripts/09-verify.sh               # all evidence -> evidence/verify-*.txt
bash scripts/10-resilience.sh           # controlled failure test

# when finished
bash scripts/99-teardown.sh
```

Every script is idempotent and prints what to screenshot at the end.

## Regenerating the documents

```bash
pip3 install --break-system-packages python-docx pymupdf
python3 report/build_report.py          # rebuilds the DOCX from screenshots/
python3 report/add_screenshots_to_pdf.py  # rebuilds the annotated PDF from the brief
```

## Versions

| Component | Version |
|---|---|
| Kubernetes (kind nodes) | v1.37.0 |
| Istio | 1.32.0 |
| MetalLB | 0.14.9 |
| kind | v0.34 |
| Docker | 29.1.3 |

## Files

```
clusters/           kind cluster definitions (pod CIDRs)
yaml/               the three deliverables from Activity 2 + the missing gateway
scripts/            numbered build + verification scripts
screenshots/        the 27 figures used in the report
report/             report sources and finished DOCX/PDF deliverables
evidence/           captured command output (created by 09-verify.sh)
RUNBOOK.md          step-by-step walkthrough with expected output
EVIDENCE.md         screenshot checklist mapped to the grading rubric
gaps-and-substitutions.md   what differs from the PDF, and why it still counts
```

## Verified results

| Claim | Evidence |
|---|---|
| Two clusters, both nodes Ready | `screenshots/02`, `03`, `26` |
| Remote secrets synced both ways | `screenshots/12` |
| Cross-cluster endpoints (peer gateway on 15443) | `screenshots/10` |
| 32/60 requests served by mesh1, 28/60 by mesh2 | `screenshots/11` |
| STRICT mTLS rejects a plaintext client (HTTP 000) | `screenshots/15` |
| 80:20 split measured at 79:21 over 100 requests | `screenshots/18` |
| Prometheus, Grafana, Kiali, Jaeger reporting live traffic | `screenshots/21`-`24` |
| Resilience: one cluster lost = no failures, subset lost = 5/30 errors | `screenshots/26` |
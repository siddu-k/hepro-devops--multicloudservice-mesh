#!/usr/bin/env python3
"""
build_report.py -- generate the DevOps Project 5 report as a .docx.

The document mirrors the structure of
  "DEVOPS PROJECT 5 Activities.pdf"
(Activity 1 Steps 1-19, Activity 2 Steps 1-26, final checklist, submission
requirements) and inserts the screenshots captured from the live local mesh at
the sections where the original document asks for them.

Figure numbering is assigned automatically in document order, so captions and
the "(see Figure N)" references in the text always agree.
"""

import os
import re
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
SHOTS = os.path.join(ROOT, "screenshots")
OUT = os.path.join(ROOT, "report", "DevOps-Project-5-Report.docx")

NAVY = RGBColor(0x1F, 0x38, 0x64)
BLUE = RGBColor(0x2E, 0x54, 0x8C)
GREY = RGBColor(0x59, 0x5F, 0x69)
DARK = RGBColor(0x1A, 0x1A, 0x1A)

BODY_PT = 10.5
CODE_PT = 7.8

# --------------------------------------------------------------------------- #
#  block list  --  the whole document is declared here, then rendered
# --------------------------------------------------------------------------- #
B = []


def h1(t): B.append(("h1", t))
def h2(t): B.append(("h2", t))
def h3(t): B.append(("h3", t))
def p(t, **k): B.append(("p", t, k))
def lead(label, text): B.append(("lead", label, text))
def bullets(items): B.append(("bullets", items))
def numbered(items): B.append(("numbered", items))
def code(t): B.append(("code", t))
def expected(t): B.append(("expected", t))
def observed(t): B.append(("observed", t))
def note(title, t): B.append(("note", title, t))
def table(headers, rows, widths=None, small=False): B.append(("table", headers, rows, widths, small))
def fig(key, caption): B.append(("fig", key, caption))
def fref(key, text): B.append(("fref", key, text))
def brk(): B.append(("brk",))
def quote(t): B.append(("quote", t))


# --------------------------------------------------------------------------- #
#  cover
# --------------------------------------------------------------------------- #
B.append(("cover",))

# --------------------------------------------------------------------------- #
#  report contents (also satisfies Step 25 of Activity 2)
# --------------------------------------------------------------------------- #
h1("Report Contents")
p("This report follows the structure of the project brief and the order of "
  "Step 25 (\u201cPrepare the Final Project Report\u201d). Each item below maps to the "
  "section where it is covered, together with the figures that prove it.")
table(
    ["#", "Required report content (Step 25)", "Covered in"],
    [
        ["1", "Project Title and Objective", "Section 1"],
        ["2", "Introduction to Multi-Cloud Service Mesh", "Section 2"],
        ["3", "Tools and Technologies Used", "Sections 4 and 5"],
        ["4", "Architecture Diagram", "Section 3, Figure 1"],
        ["5", "AWS EKS and Google GKE Cluster Setup", "Activity 1, Parts A\u2013C (Figures 2\u20135)"],
        ["6", "Istio Installation and Configuration", "Activity 1, Part D (Figures 6\u201310)"],
        ["7", "Cross-Cluster Communication", "Activity 1 Part F, Activity 2 Part E (Figures 8, 9, 13, 25)"],
        ["8", "Bookinfo Application Deployment", "Activity 1, Part E (Figures 11\u201312)"],
        ["9", "Mutual TLS Implementation", "Activity 2, Part A (Figures 14\u201315)"],
        ["10", "Traffic Management Configuration", "Activity 2, Part B (Figures 16\u201318)"],
        ["11", "Prometheus, Grafana, Kiali and Jaeger Integration", "Activity 2, Part C (Figures 19\u201324)"],
        ["12", "Testing and Verification Results", "Activity 2, Parts D\u2013F (Figures 25\u201327)"],
        ["13", "Challenges Faced and Solutions", "Section 12"],
        ["14", "Conclusion", "Section 13"],
    ],
    widths=[1.0, 9.4, 6.6], small=True)

note("How to read this report",
     "Every step of the original activities is reproduced in order. Where the brief "
     "gives a cloud command, the command that was actually executed is shown in the "
     "same place, and the screenshot taken from the running system follows the step "
     "that asks for it. Appendix A holds the YAML files, Appendix B the evidence "
     "inventory and Appendix C the scripts needed to reproduce the whole environment.")

brk()

# --------------------------------------------------------------------------- #
#  1  title and objective
# --------------------------------------------------------------------------- #
h1("1. Project Title and Objective")
lead("Project title", "DevOps Project 5 \u2014 Multi-Cloud Service Mesh Implementation")
lead("Objective", "Build a secure and observable communication environment between "
                  "microservices deployed across multiple Kubernetes clusters using the "
                  "Istio service mesh.")
p("The project brief asks for two Kubernetes clusters on two different clouds, a shared "
  "Istio mesh spanning both of them, the Bookinfo sample application deployed with Envoy "
  "sidecars, mutual TLS between services, weighted traffic routing between two versions of "
  "the reviews service, and a monitoring stack made of Prometheus, Grafana, Kiali and Jaeger.")
p("This report documents that implementation. It was built and verified end to end. The two "
  "clusters are real, separate Kubernetes clusters with separate API servers, separate pod "
  "networks and separate ingress addresses; the only difference from the brief is that they "
  "run as kind clusters inside one Ubuntu host instead of EKS and GKE. Section 5 explains the "
  "substitution in detail and why every piece of evidence that the brief asks for is still "
  "genuine evidence about a multi-cluster Istio mesh.")

# --------------------------------------------------------------------------- #
#  2  introduction
# --------------------------------------------------------------------------- #
h1("2. Introduction to Multi-Cloud Service Mesh")
p("A service mesh moves the concerns that every microservice would otherwise re-implement "
  "\u2014 retries, mutual authentication, traffic splitting, telemetry \u2014 into a sidecar proxy "
  "that is injected next to each workload. The application keeps making plain HTTP calls to a "
  "Kubernetes Service name; the proxy beside it performs the TLS handshake, applies the routing "
  "policy and reports metrics and spans.")
p("When the mesh spans more than one cluster, two extra problems appear. The first is "
  "discovery: each control plane must learn the endpoints that live in the other cluster. The "
  "second is reachability: pod addresses in one cluster are not routable from the other, so "
  "cross-cluster traffic has to be sent through a gateway. Istio solves both with the "
  "primary-remote, multi-network topology used here:")
bullets([
    "each cluster runs its own istiod, so each cluster keeps working if the other one is lost;",
    "the two control planes exchange \u201cremote secrets\u201d \u2014 kubeconfigs that let each istiod watch "
    "the other cluster\u2019s services and endpoints;",
    "a dedicated east-west gateway in each cluster terminates the cross-cluster connection on "
    "port 15443 and forwards traffic by SNI, so a reviews pod in cluster 1 can reach a reviews "
    "pod in cluster 2 even though the pod networks are isolated;",
    "both clusters share one root CA, otherwise the mutual TLS handshake between the two halves "
    "of the mesh fails.",
])
p("The result is one logical mesh with two failure domains, which is exactly what the "
  "\u201cmulti-cloud\u201d part of the title is about.")

# --------------------------------------------------------------------------- #
#  3  architecture
# --------------------------------------------------------------------------- #
h1("3. Architecture Diagram")
fig("00-architecture",
    "Reference architecture of the implemented mesh: two independent kind clusters, each with "
    "its own control plane, ingress gateway and east-west gateway, joined only through the "
    "docker underlay network. Addresses and component names are the ones used throughout this report.")
p("The diagram shows the addresses that appear in every screenshot that follows:")
table(
    ["Component", "Cluster 1 \u2014 mesh1", "Cluster 2 \u2014 mesh2"],
    [
        ["Role in the brief", "AWS EKS (primary)", "Google GKE (remote)"],
        ["kubectl context", "kind-mesh1", "kind-mesh2"],
        ["Node internal IP", "172.30.0.3", "172.30.0.2"],
        ["Pod CIDR", "10.244.0.0/16", "10.245.0.0/16"],
        ["Ingress gateway VIP", "172.30.0.200:80", "172.30.0.210:80"],
        ["East-west gateway VIP", "172.30.0.201:15443", "172.30.0.211:15443"],
        ["istiod", "istiod-54f9594b8-kvq89", "istiod-568446d999-8wksk"],
    ],
    widths=[4.6, 6.2, 6.2])

# --------------------------------------------------------------------------- #
#  4  tools
# --------------------------------------------------------------------------- #
h1("4. Tools and Technologies Used")
p("The brief lists a cloud-oriented stack. The table keeps the brief\u2019s wording in the left "
  "column and records what was actually used to produce the evidence in this report.")
table(
    ["Technology (brief)", "Implementation used here", "Version / detail"],
    [
        ["Cloud platforms: AWS (EKS) and Google Cloud (GKE)", "Two kind clusters on one Ubuntu host", "kind v0.34.0, Kubernetes v1.37.0"],
        ["Container orchestration: Kubernetes", "Kubernetes in kind node containers", "v1.37.0, containerd 2.3.4"],
        ["Container runtime", "Docker Engine inside WSL2", "29.1.3"],
        ["Service mesh: Istio", "Istio, primary-remote multi-network topology", "1.32.0 (ambient-free, sidecar mode)"],
        ["Proxy: Envoy", "Envoy shipped with Istio, native sidecars", "istio-proxy 1.32.0"],
        ["Monitoring: Prometheus and Grafana", "Istio sample add-ons", "Prometheus, Grafana 11"],
        ["Visualisation: Kiali", "Istio sample add-on", "Kiali 2.x"],
        ["Distributed tracing: Jaeger", "Istio sample add-on, zipkin receiver", "Jaeger v2"],
        ["Configuration: YAML", "Istio CRDs applied with kubectl", "PeerAuthentication, DestinationRule, VirtualService"],
        ["Command line: Linux terminal / Cloud Shell", "Ubuntu 24.04 LTS on WSL2", "bash, kubectl, istioctl, kind, docker"],
        ["Load balancer", "MetalLB on a shared docker bridge", "VIP pool 172.30.0.200-219"],
    ],
    widths=[5.2, 6.2, 5.6], small=True)
p("The installed client versions are shown in Figure 2, at the step where the brief asks for "
  "that check.")

# --------------------------------------------------------------------------- #
#  5  environment and substitution
# --------------------------------------------------------------------------- #
h1("5. Implementation Environment and Cloud Substitution")
p("The brief asks for an AWS account and a Google Cloud account. Neither was used: the whole "
  "project runs locally, with no cloud subscription, no cluster charges and no data leaving the "
  "machine. This does not weaken the result, because the things the brief wants to see are "
  "properties of the mesh, not of the cloud provider:")
bullets([
    "two clusters with two independent control planes, two API servers and two kubectl contexts;",
    "two pod networks with no route between them, so cross-cluster traffic must use gateways;",
    "real load-balancer addresses for the ingress and east-west gateways;",
    "a shared certificate authority, strict mTLS, weighted routing, telemetry and tracing.",
])
p("The table records the exact substitution so that the evidence can be read correctly.")
table(
    ["Cloud item in the brief", "Local equivalent", "Why it is equivalent for this project"],
    [
        ["EKS cluster eks-mesh", "kind cluster mesh1 (control-plane node 172.30.0.3)",
         "Real Kubernetes API server, scheduler, kubelet and CNI; separate from mesh2 in every respect."],
        ["GKE cluster gke-mesh", "kind cluster mesh2 (control-plane node 172.30.0.2)",
         "Second, independent cluster with its own pod CIDR 10.245.0.0/16."],
        ["AWS NLB / GCP TCP load balancer", "MetalLB VIPs 172.30.0.200-219 on the mesh-underlay bridge",
         "Gives the gateways stable, externally reachable IPs, which is what the mesh needs."],
        ["Cross-cloud VPC peering", "Shared docker bridge mesh-underlay 172.30.0.0/24",
         "Nodes can reach each other, pods cannot: the same topology the multi-network Istio guide assumes."],
        ["IAM / cloud credentials", "Local kubeconfig contexts kind-mesh1 and kind-mesh2",
         "Authentication and authorisation still happen, just against the kind API servers."],
    ],
    widths=[4.6, 5.6, 6.8], small=True)
note("Statement of scope",
     "All addresses, pod names, counts and timings quoted in this report were produced by the "
     "running system described above. The commands shown in each step are the commands that were "
     "executed. Where the brief prescribes a cloud command (eksctl, gcloud, aws), that command is "
     "reproduced for completeness and immediately followed by the local command that replaced it.")

# --------------------------------------------------------------------------- #
#  ACTIVITY 1
# --------------------------------------------------------------------------- #
brk()
h1("ACTIVITY 1: MULTI-CLOUD KUBERNETES CLUSTER SETUP AND ISTIO SERVICE MESH DEPLOYMENT")

h2("Objective")
p("In this activity, two Kubernetes clusters are created, Istio Service Mesh is installed, "
  "communication between the clusters is configured, and a sample microservices application is "
  "deployed. Completing the activity establishes the infrastructure and service mesh foundation "
  "required for the complete project.")

h2("Tools Required")
table(
    ["#", "Tool required by the brief", "Used in this implementation"],
    [
        ["1", "AWS Account", "Not required \u2014 local kind cluster mesh1"],
        ["2", "Google Cloud Account", "Not required \u2014 local kind cluster mesh2"],
        ["3", "AWS CLI", "Not required (no AWS calls are made)"],
        ["4", "Google Cloud CLI (gcloud)", "Not required (no GCP calls are made)"],
        ["5", "kubectl", "v1.37.1"],
        ["6", "eksctl", "Replaced by kind v0.34.0"],
        ["7", "Istio CLI (istioctl)", "1.32.0 at /root/istio-1.32.0/bin"],
        ["8", "Git", "Project scripts are plain bash in scripts/"],
    ],
    widths=[1.0, 7.4, 8.6], small=True)

note("Important",
     "Creating EKS and GKE clusters may incur cloud charges. Because this implementation is fully "
     "local, no cloud account, quota or billing is involved, and nothing has to be deleted "
     "afterwards except the two kind clusters (scripts/99-teardown.sh).")

# ---- PART A
h2("PART A: Prepare the Working Environment")

h3("Step 1: Open a Linux Terminal")
p("The brief allows AWS CloudShell, Google Cloud Shell, or a Linux machine with the required "
  "cloud CLIs. This implementation uses the third option: an Ubuntu 24.04 LTS environment on "
  "WSL2, with Docker, kubectl, kind and istioctl installed.")
code("""$ uname -sr
Linux 6.18.33.2-microsoft-standard-WSL2
$ cat /etc/os-release | head -2
PRETTY_NAME="Ubuntu 24.04.3 LTS"
NAME="Ubuntu\"""")

h3("Step 2: Check the Installed Tools")
p("The brief verifies the cloud CLIs. In this implementation the equivalent check covers the "
  "tools that are actually used, because kubectl and istioctl are the only clients that talk to "
  "anything.")
code("""$ kubectl version --client
$ istioctl version --remote=false
$ kind version
$ docker --version""")
p("These commands verify whether the required tools are installed.")
expected("The terminal should display the installed versions of the tools.")
observed("kubectl v1.37.1, istioctl 1.32.0, kind v0.34.0, Docker 29.1.3.")
fig("01-tool-versions",
    "Step 2 \u2014 installed tooling. kubectl 1.37.1, istioctl 1.32.0, kind 0.34.0 and Docker 29.1.3.")

h3("Step 3: Configure AWS Access")
p("The brief runs aws configure and aws sts get-caller-identity. No AWS account is used, so this "
  "step has no cloud equivalent. Its purpose \u2014 proving that the client is authenticated against "
  "the environment it will create resources in \u2014 is served by the Docker engine and the kind "
  "contexts created in Steps 5 and 8.")
code("""$ docker info --format '{{.ServerVersion}} {{.Driver}}'
29.1.3 overlay2""")

h3("Step 4: Configure Google Cloud Access")
p("The brief runs gcloud init and gcloud config list. As with Step 3 there is no Google Cloud "
  "project; the second cluster is a local kind cluster, and the \u201cproject/zone\u201d equivalent is "
  "the kind cluster name and its docker network.")
code("""$ kind get clusters
mesh1
mesh2""")
p("From this point on, every command is tagged with --context kind-mesh1 or --context kind-mesh2, "
  "which plays the role of the cloud project selector.")

# ---- PART B
h2("PART B: Create the AWS Kubernetes Cluster")

h3("Step 5: Create an EKS Cluster")
p("The brief command is:")
code("""eksctl create cluster \\
--name eks-mesh \\
--region us-east-1 \\
--nodes 2 \\
--node-type t3.medium""")
lead("Explanation (as in the brief)",
     "eksctl create cluster creates a Kubernetes cluster; --name assigns the cluster name; "
     "--region selects the region; --nodes 2 creates two worker nodes; --node-type specifies the "
     "worker node type.")
p("The command executed in this implementation creates the equivalent cluster with kind, on its "
  "own docker bridge and its own MetalLB address range:")
code("""kind create cluster --name mesh1 \\
  --config kind-mesh1.yaml          # podSubnet 10.244.0.0/16, node on mesh-underlay
docker network connect mesh-underlay mesh1-control-plane
metallb: address pool 172.30.0.200-209
kubectl --context kind-mesh1 get nodes""")
expected("The cluster is created and its node becomes Ready.")
observed("kind cluster mesh1 came up with one control-plane node and a pod network of its own.")

h3("Step 6: Verify the AWS Cluster")
code("""kubectl get nodes --context kind-mesh1
kubectl get pods -A --context kind-mesh1""")
expected("The Kubernetes nodes should appear, show Ready, and system pods should be running.")
observed("mesh1-control-plane is Ready (v1.37.0, internal IP 172.30.0.3) and every kube-system pod "
         "is Running.")
fig("02-nodes-mesh1",
    "Step 6 \u2014 cluster 1 (mesh1) node information. The node is Ready, Kubernetes v1.37.0, "
    "internal address 172.30.0.3 on the shared underlay network.")

# ---- PART C
h2("PART C: Create the Google Cloud Kubernetes Cluster")

h3("Step 7: Create a GKE Cluster")
p("The brief command is:")
code("""gcloud container clusters create gke-mesh \\
--zone us-central1-a \\
--num-nodes 2""")
p("The equivalent local command creates the second, independent cluster with a different pod "
  "CIDR so that the two clusters cannot reach each other\u2019s pods directly:")
code("""kind create cluster --name mesh2 \\
  --config kind-mesh2.yaml          # podSubnet 10.245.0.0/16, node on mesh-underlay
docker network connect mesh-underlay mesh2-control-plane
metallb: address pool 172.30.0.210-219""")
expected("The second cluster is created and its node becomes Ready.")
observed("mesh2-control-plane is Ready, Kubernetes v1.37.0, internal IP 172.30.0.2.")
fig("03-nodes-mesh2",
    "Step 7 \u2014 cluster 2 (mesh2) node information: a separate API server and a separate node, "
    "with pod CIDR 10.245.0.0/16.")

h3("Step 8: Connect kubectl to the GKE Cluster")
p("The brief updates the kubeconfig with gcloud container clusters get-credentials. kind writes "
  "the equivalent contexts automatically:")
code("""$ kind export kubeconfig --name mesh2
$ kubectl config get-contexts kind-mesh1
$ kubectl config get-contexts kind-mesh2""")
expected("Both contexts are present and selectable, exactly like the EKS and GKE contexts.")
observed("kind-mesh1 and kind-mesh2 are both listed; kind-mesh2 is current.")
fig("04-kubectl-contexts",
    "Step 8 \u2014 the two kubectl contexts that stand in for the EKS and GKE contexts.")

h3("Step 9: Verify Both Clusters")
code("""kubectl get nodes --context kind-mesh1
kubectl get nodes --context kind-mesh2""")
expected("Both clusters should be accessible and their worker nodes should show Ready.")
observed("mesh1-control-plane and mesh2-control-plane are both Ready, each in its own cluster.")

# ---- PART D
h2("PART D: Install Istio Service Mesh")

h3("Step 10: Download Istio")
code("""curl -L https://istio.io/downloadIstio | sh -
cd istio-1.32.0
export PATH=$PWD/bin:$PATH
istioctl version""")
expected("The terminal should display the installed Istio CLI version.")
observed("client version: 1.32.0 (Figure 2).")

h3("Step 11: Install Istio in the Primary Cluster")
p("The brief exports the two contexts and installs the demo profile in the primary cluster. In "
  "this implementation the same install is driven by an IstioOperator manifest, because the "
  "multi-network topology needs an east-west gateway in each cluster and a tracing provider that "
  "the demo profile does not create:")
code("""export CTX_CLUSTER1=kind-mesh1
export CTX_CLUSTER2=kind-mesh2

istioctl install --context "$CTX_CLUSTER1" -y -f - <<'EOF'
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
spec:
  profile: default
  meshConfig:
    extensionProviders:
      - name: jaeger
        zipkin:
          service: jaeger-collector.istio-system.svc.cluster.local
          port: 9411
  components:
    ingressGateways:
      - name: istio-ingressgateway
        enabled: true
      - name: istio-eastwestgateway     # required for multi-network
        enabled: true
        label:
          topology.istio.io/network: mesh1
EOF

kubectl get pods -n istio-system --context "$CTX_CLUSTER1\"""")
p("The same operator manifest is applied to mesh2 with network label mesh2, which gives each "
  "cluster its own control plane and its own pair of gateways.")
expected("istiod, the ingress gateway and the east-west gateway are running in the primary cluster.")
observed("istiod, istio-ingressgateway and istio-eastwestgateway are Running; the observability "
         "add-ons are added later in Activity 2.")
fig("05-istio-pods-mesh1",
    "Step 11 / Step 14 \u2014 Istio control plane and both gateways in cluster 1 (mesh1). The "
    "Jaeger, Kiali, Grafana and Prometheus pods are added in Activity 2, Part C.")

h3("Step 12: Prepare the Application Namespace")
code("""kubectl label namespace default istio-injection=enabled --context kind-mesh1
kubectl label namespace default istio-injection=enabled --context kind-mesh2""")
p("This enables automatic Envoy sidecar injection for new application pods deployed in the "
  "namespace. The label is set in both clusters so that the Bookinfo workloads on either side of "
  "the mesh receive a proxy.")

h3("Step 13: Configure the GKE Cluster as a Remote Cluster")
p("The brief lists the nine steps of the primary-remote, different-networks procedure. Each one "
  "is implemented here, with the local equivalents of the cloud resources:")
table(
    ["#", "Procedure step (brief)", "Implementation"],
    [
        ["1", "Set the network identity of each cluster", "topology.istio.io/network=mesh1 / mesh2 on the gateway pods and the istio-system namespace"],
        ["2", "Configure the AWS cluster as primary", "istioctl install with profile default in kind-mesh1"],
        ["3", "Install its east-west gateway", "istio-eastwestgateway component, MetalLB VIP 172.30.0.201:15443"],
        ["4", "Expose the primary control plane", "samples/multicluster/expose-services.yaml (istiod, ingress, egress by SNI)"],
        ["5", "Configure GKE as the remote cluster", "istioctl install in kind-mesh2 with its own istiod and network label"],
        ["6", "Install the remote Istio configuration", "expose-services.yaml applied in kind-mesh2"],
        ["7", "Install the remote secret", "istioctl create-remote-secret both directions, server address = peer node IP:6443"],
        ["8", "Install the GKE east-west gateway", "east-west gateway in mesh2, VIP 172.30.0.211:15443"],
        ["9", "Expose services across both clusters", "shared root CA (cacerts) + Telemetry + Bookinfo in both clusters"],
    ],
    widths=[1.0, 7.0, 9.0], small=True)
code("""# 7. exchange remote secrets - each istiod watches the other cluster
istioctl create-remote-secret --context kind-mesh1 --name mesh1 \\
  --server https://172.30.0.3:6443 | kubectl apply -f - --context kind-mesh2
istioctl create-remote-secret --context kind-mesh2 --name mesh2 \\
  --server https://172.30.0.2:6443 | kubectl apply -f - --context kind-mesh1

# 8. second east-west gateway is part of the mesh2 install
kubectl get svc -n istio-system istio-eastwestgateway --context kind-mesh2

# 9. one root of trust for both halves of the mesh
kubectl create secret generic cacerts -n istio-system --context kind-mesh1 \\
  --from-file=ca-cert.pem --from-file=ca-key.pem \\
  --from-file=root-cert.pem --from-file=cert-chain.pem""")
note("Why the shared CA is not optional",
     "Each istiod generates its own self-signed root by default. Across two clusters that means "
     "the proxy in mesh1 presents a certificate signed by CA-A while the proxy in mesh2 only "
     "trusts CA-B, so every cross-cluster handshake fails with a 503 that looks like a networking "
     "fault. Scripts 03b-shared-ca.sh installs Istio's sample plugin CA material in both clusters "
     "and restarts the proxies so that every workload gets a certificate from the shared root.")
expected("Both clusters are registered with each other and each has an east-west gateway with a "
         "stable address.")
observed("istioctl remote-clusters reports STATUS synced in both directions, and the east-west "
         "gateways hold VIPs 172.30.0.201 and 172.30.0.211 on port 15443.")
fig("06-istio-pods-mesh2",
    "Step 13 \u2014 Istio control plane and both gateways in cluster 2 (mesh2), the remote half of "
    "the mesh.")
fig("12-remote-clusters",
    "Step 13 \u2014 remote cluster registration. mesh2 is synced into mesh1's control plane (and "
    "mesh1 into mesh2's), which is what makes cross-cluster service discovery work.")
fig("13-gateway-vips",
    "Step 13 \u2014 gateway addresses in both clusters: ingress 172.30.0.200 / 172.30.0.210 on "
    "port 80, east-west 172.30.0.201 / 172.30.0.211 on port 15443.")

h3("Step 14: Verify the Istio Installation")
code("""kubectl get pods -n istio-system --context "$CTX_CLUSTER1"
kubectl get pods -n istio-system --context "$CTX_CLUSTER2"
istioctl proxy-status --context "$CTX_CLUSTER1\"""")
expected("The Istio control plane, gateway components and applicable Envoy proxies should be "
         "operational.")
observed("Every proxy in both clusters reports SYNCED with four subscribed types (CDS, LDS, EDS, "
         "RDS); the east-west gateways subscribe to three.")
fig("09-proxy-status",
    "Step 14 \u2014 istioctl proxy-status for both clusters. Every proxy is synchronised with its "
    "own istiod: CDS, LDS, EDS and RDS are all subscribed.")

# ---- PART E
h2("PART E: Deploy the Sample Microservices Application")

h3("Step 15: Deploy the Bookinfo Application")
p("Bookinfo consists of four microservices \u2014 product page, details, reviews and ratings \u2014 with "
  "three versions of reviews (v1 without ratings, v2 and v3 with ratings in different colours). "
  "It is deployed in both clusters so that the mesh has real remote endpoints to discover.")
code("""kubectl apply -f samples/bookinfo/platform/kube/bookinfo.yaml --context kind-mesh1
kubectl apply -f samples/bookinfo/platform/kube/bookinfo.yaml --context kind-mesh2

kubectl apply -f samples/bookinfo/networking/bookinfo-gateway.yaml --context kind-mesh1
kubectl apply -f samples/bookinfo/networking/destination-rule-all.yaml --context kind-mesh1""")
p("The namespace was labelled for injection in Step 12, so each pod is created with its Envoy "
  "sidecar already attached.")

h3("Step 16: Check the Application Pods")
code("""kubectl get pods --context "$CTX_CLUSTER1"
kubectl get services --context "$CTX_CLUSTER1\"""")
p("The brief asks whether the application pods are running and whether the corresponding services "
  "have been created.")
expected("All Bookinfo pods are Running with 2/2 containers, and the four services exist.")
observed("productpage, details, reviews v1/v2/v3 and ratings are 2/2 Running; the two helper pods "
         "traffic-client (2/2) and mtls-probe (1/1, deliberately without a sidecar) are also present.")
fig("07-bookinfo-pods",
    "Step 16 \u2014 Bookinfo application pods in cluster 1. Every application pod shows 2/2, i.e. the "
    "application container plus its Envoy sidecar. traffic-client is the in-mesh client used for "
    "the request tests, mtls-probe is the sidecar-less pod used to prove that mTLS is enforced.")

h3("Step 17: Verify Envoy Sidecar Injection")
code("""kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{" : "}\\
{.spec.containers[*].name}{"\\n"}{end}' --context "$CTX_CLUSTER1\"""")
p("The brief asks to look for the istio-proxy container next to the application containers. Istio "
  "1.32 implements the sidecar as a native sidecar, which the API server represents as an "
  "initContainer with restartPolicy: Always, so the column that shows it is initContainers:")
code("""kubectl get pods -n default --context kind-mesh1 -o custom-columns=\\
'POD:.metadata.name,APP:.spec.containers[*].name,SIDECAR:.spec.initContainers[*].name'""")
expected("Application pods should have the Envoy proxy sidecar injected.")
observed("Every Bookinfo pod lists istio-init,istio-proxy; mtls-probe lists none.")
fig("08-sidecar-injection",
    "Step 17 \u2014 Envoy sidecar injection. Each workload carries istio-init and istio-proxy; the "
    "mtls-probe pod intentionally has no proxy and is used in Activity 2 to prove that STRICT mTLS "
    "rejects plaintext clients.")

# ---- PART F
h2("PART F: Verify the Service Mesh")

h3("Step 18: Check Istio Service Information")
code("""istioctl proxy-status --context "$CTX_CLUSTER1"
kubectl get svc -A --context "$CTX_CLUSTER1"
kubectl get svc -A --context "$CTX_CLUSTER2\"""")
p("The proxy status output in Figure 10 shows both halves of the mesh side by side, and the "
  "gateway addresses in Figure 9 show the services that were created for cross-cluster traffic.")

h3("Step 19: Record the Results")
p("The brief requires screenshots for nine items. Each one is produced by the live system and "
  "referenced below.")
table(
    ["#", "Evidence required by the brief", "Figure"],
    [
        ["1", "Successful AWS EKS cluster creation", "Figure 3"],
        ["2", "Successful Google GKE cluster creation", "Figure 4"],
        ["3", "Kubernetes nodes showing Ready", "Figures 3 and 4"],
        ["4", "Istio installation in both clusters", "Figures 6 and 7"],
        ["5", "Istio system pods running", "Figures 6 and 7"],
        ["6", "Bookinfo application pods running", "Figure 11"],
        ["7", "Envoy sidecar injection", "Figure 12"],
        ["8", "Istio proxy status", "Figure 10"],
        ["9", "Cross-cluster service discovery configuration", "Figures 8, 9 and 13"],
    ],
    widths=[1.0, 10.6, 5.4], small=True)
p("The ninth item deserves a note. 'kubectl get endpoints' only ever lists the pods of the local "
  "cluster, because each cluster keeps its own endpoints object. In a multi-network mesh the "
  "remote pods are represented in Envoy's endpoint list by the east-west gateway of the other "
  "cluster, so the authoritative check is 'istioctl proxy-config endpoint':")
code("""$ istioctl -n default proxy-config endpoint productpage-v1-7b5d6847cb-xcm4w \\
    --context kind-mesh1 --cluster 'outbound|9080||reviews.default.svc.cluster.local'

ENDPOINT               STATUS      OUTLIER CHECK     CLUSTER
10.244.0.17:9080       HEALTHY     OK                outbound|9080||reviews.default.svc.cluster.local
10.244.0.18:9080       HEALTHY     OK                outbound|9080||reviews.default.svc.cluster.local
10.244.0.20:9080       HEALTHY     OK                outbound|9080||reviews.default.svc.cluster.local
172.30.0.211:15443     HEALTHY     OK                outbound|9080||reviews.default.svc.cluster.local""")
p("The three 10.244.x.x addresses are the local reviews pods of mesh1. The fourth entry, "
  "172.30.0.211:15443, is mesh2's east-west gateway: it stands for every reviews pod in the other "
  "cluster, and traffic sent to it is forwarded by SNI. If the remote secret were not syncing, "
  "only the 10.244.x.x entries would appear.")
fig("10-cross-cluster-endpoints",
    "Step 19, item 9 \u2014 cross-cluster service discovery. Envoy lists the three local reviews pods "
    "and, as a fourth endpoint, the mesh2 east-west gateway 172.30.0.211:15443. This is the "
    "evidence that the two clusters share one endpoint list.")

h2("Expected Outcome of Activity 1")
p("At the end of this activity the implementation has:")
bullets([
    "two Kubernetes clusters, each with its own control plane and its own node;",
    "both clusters connected through Istio, with synced remote secrets in both directions;",
    "Istio Service Mesh installed with ingress and east-west gateways in both clusters;",
    "cross-cluster service discovery and connectivity, proven through the Envoy endpoint list;",
    "the Bookinfo sample application deployed in both clusters;",
    "Envoy sidecar injection enabled and verified on every application pod;",
    "the mesh infrastructure verified end to end.",
])
lead("Activity 1 deliverable",
     "A working multi-cloud Kubernetes environment with an Istio service mesh and deployed "
     "sample microservices.")

# --------------------------------------------------------------------------- #
#  ACTIVITY 2
# --------------------------------------------------------------------------- #
brk()
h1("ACTIVITY 2: SECURE COMMUNICATION, TRAFFIC MANAGEMENT AND OBSERVABILITY")

h2("Objective")
p("Configure secure communication between microservices using mutual TLS, implement traffic "
  "routing policies, install monitoring and observability tools, and test communication between "
  "the Kubernetes clusters. This activity completes the project by implementing the security, "
  "traffic management, monitoring and validation features.")

h2("Tools Required")
table(
    ["#", "Tool", "Used in this implementation"],
    [
        ["1", "Existing clusters from Activity 1", "kind-mesh1 and kind-mesh2, still running"],
        ["2", "Istio Service Mesh", "1.32.0, sidecar mode"],
        ["3", "kubectl", "v1.37.1"],
        ["4", "istioctl", "1.32.0"],
        ["5", "Prometheus", "Istio sample add-on, scraping the Envoy proxies"],
        ["6", "Grafana", "Istio Mesh dashboard"],
        ["7", "Kiali", "service graph, namespace default"],
        ["8", "Jaeger", "zipkin receiver on jaeger-collector:9411"],
    ],
    widths=[1.0, 7.0, 9.0], small=True)

# ---- PART A
h2("PART A: Implement Mutual TLS (mTLS)")

h3("Step 1: Understand the Purpose of mTLS")
p("Mutual TLS allows both communicating services to authenticate each other and encrypt their "
  "communication. With Istio the certificates are issued by the mesh itself: istiod acts as the "
  "certificate authority and rotates each proxy's certificate automatically. In STRICT mode a "
  "workload accepts only TLS connections, so a plaintext client is rejected before any HTTP "
  "request is processed.")

h3("Step 2: Create the PeerAuthentication Configuration")
p("File peer-authentication.yaml (full text in Appendix A):")
code("""apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: default
spec:
  mtls:
    mode: STRICT""")
p("The name 'default' and the absence of a selector mean the policy applies to the whole "
  "namespace. The brief shows apiVersion security.istio.io/v1beta1; v1 is the served version in "
  "Istio 1.32 and is what was applied.")

h3("Step 3: Apply the mTLS Configuration")
code("""kubectl apply -f peer-authentication.yaml --context kind-mesh1
kubectl apply -f peer-authentication.yaml --context kind-mesh2""")
p("The policy is applied to both clusters, because the mesh has two control planes and each one "
  "enforces only the policies it knows about.")

h3("Step 4: Verify the mTLS Policy")
code("""kubectl get peerauthentication --context kind-mesh1
kubectl describe peerauthentication default --context kind-mesh1
kubectl get peerauthentication --context kind-mesh2""")
expected("The PeerAuthentication policy should show STRICT as the configured mTLS mode.")
observed("default STRICT in both clusters.")
fig("14-peerauthentication",
    "Step 4 \u2014 the PeerAuthentication object returned by the API server, with spec.mtls.mode: STRICT.")
p("A policy that only describes itself proves nothing, so the enforcement was tested with two "
  "clients: traffic-client runs inside the mesh and has a sidecar, mtls-probe deliberately has "
  "none.")
code("""kubectl -n default exec traffic-client --context kind-mesh1 -- \\
  curl -s -o /dev/null -w "%{http_code}" http://reviews:9080/reviews/0
kubectl -n default exec mtls-probe    --context kind-mesh1 -- \\
  curl -s -o /dev/null -w "%{http_code}" http://reviews:9080/reviews/0""")
expected("Workloads inside the mesh succeed; a client without a certificate cannot connect.")
observed("in-mesh pod -> HTTP 200; pod without sidecar -> HTTP 000 with curl exit code 56 "
         "(connection reset by the server-side proxy).")
fig("15-mtls-test",
    "Step 4 \u2014 mTLS enforcement test. The in-mesh client gets HTTP 200 through the encrypted "
    "tunnel; the identical request from a pod without a sidecar is reset (HTTP 000), which is "
    "exactly what STRICT mode should do.")
note("Note (from the brief)",
     "All participating workloads must have compatible Istio proxy injection and certificate "
     "configuration for strict mTLS to work. This is why the sidecar-less mtls-probe is the only "
     "pod that fails, and why the shared root CA from Step 13 was installed before this test.")

# ---- PART B
h2("PART B: Configure Traffic Management and Routing")

h3("Step 5: Understand Traffic Routing")
p("Istio allows administrators to control how requests are distributed between different versions "
  "of a microservice. For this activity the traffic distribution is:")
bullets(["Reviews Version 1: 80%", "Reviews Version 2: 20%"])

h3("Step 6: Create a DestinationRule")
p("File reviews-destination-rule.yaml (full text in Appendix A) defines the subsets by pod label:")
code("""apiVersion: networking.istio.io/v1
kind: DestinationRule
metadata:
  name: reviews
  namespace: default
spec:
  host: reviews
  subsets:
    - name: v1
      labels: { version: v1 }
    - name: v2
      labels: { version: v2 }
    - name: v3
      labels: { version: v3 }""")

h3("Step 7: Apply the DestinationRule")
code("""kubectl apply -f reviews-destination-rule.yaml --context kind-mesh1""")
p("The DestinationRule is applied to the primary cluster, whose control plane shares it with the "
  "remote cluster and whose ingress gateway serves the product page.")

h3("Step 8: Create a VirtualService")
p("File reviews-virtual-service.yaml (full text in Appendix A):")
code("""apiVersion: networking.istio.io/v1
kind: VirtualService
metadata:
  name: reviews
  namespace: default
spec:
  hosts:
    - reviews
  http:
    - route:
        - destination: { host: reviews, subset: v1 }
          weight: 80
        - destination: { host: reviews, subset: v2 }
          weight: 20""")

h3("Step 9: Apply the VirtualService")
code("""kubectl apply -f reviews-virtual-service.yaml --context kind-mesh1""")

h3("Step 10: Verify the Traffic Rules")
code("""kubectl get virtualservice --context kind-mesh1
kubectl get destinationrule --context kind-mesh1
kubectl describe virtualservice reviews --context kind-mesh1""")
expected("Istio should have the routing rules configured to distribute traffic between Reviews v1 "
         "and v2 at an 80:20 weight.")
observed("The describe output shows subset v1 weight 80 and subset v2 weight 20, and DestinationRule "
         "reviews exposes the three subsets.")
fig("16-virtualservice",
    "Step 10 \u2014 VirtualService reviews as returned by the API server: 80% to subset v1, 20% to "
    "subset v2.")
fig("17-destinationrule",
    "Step 10 \u2014 DestinationRule reviews: the v1, v2 and v3 subsets selected by the version pod label.")
p("A weight in a specification is a promise; the measurement is the evidence. The client sends "
  "100 requests to the reviews service and counts the version reported by each response:")
code("""for i in $(seq 1 100); do
  curl -s http://reviews:9080/reviews/0 | grep -o 'reviews-v[0-9]'
done | sort | uniq -c""")
observed("v1=79 v2=21 v3=0 fail=0 \u2014 an 79:21 split against a configured 80:20, with v3 never "
         "selected because it carries no weight.")
fig("18-traffic-split",
    "Step 10 \u2014 measured split over 100 requests: v1=79, v2=21, v3=0, fail=0. The 80:20 weight "
    "is being applied by the proxy, not merely stored in the configuration.")

# ---- PART C
h2("PART C: Install the Monitoring and Observability Stack")

h3("Step 11: Install Prometheus, Grafana, Kiali and Jaeger")
code("""kubectl apply -f samples/addons/ --context kind-mesh1""")
p("The sample add-ons are installed individually so that a missing manifest in a given Istio "
  "release is reported rather than silently skipped. Tracing needs one extra resource, applied to "
  "both clusters after Jaeger is running:")
code("""apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
  name: mesh-default
  namespace: istio-system
spec:
  tracing:
    - providers:
        - name: jaeger
      randomSamplingPercentage: 100.0""")
p("The 100% sampling is a lab decision: it makes every request appear as a trace so that the "
  "screenshots are reproducible. The provider itself (jaeger-collector.istio-system:9411) is "
  "declared in meshConfig by the IstioOperator in Activity 1, Step 11.")

h3("Step 12: Verify the Monitoring Components")
code("""kubectl get pods -n istio-system --context kind-mesh1
kubectl rollout status deployment/kiali -n istio-system --context kind-mesh1
kubectl get svc -n istio-system --context kind-mesh1""")
expected("The installed monitoring components should reach their running and ready states.")
observed("Prometheus (2/2), Grafana, Kiali and Jaeger are Running, and the four services plus "
         "jaeger-collector and tracing are present.")
fig("19-observability-pods",
    "Step 12 \u2014 Prometheus, Grafana, Kiali and Jaeger pods running in istio-system.")
fig("20-observability-services",
    "Step 12 \u2014 the service objects behind the dashboards: grafana 3000, kiali 20001/9090, "
    "prometheus 9090, jaeger-collector 9411/14268/14250 and tracing 80/16685.")

h3("Step 13: Open the Kiali Dashboard")
p("The brief uses istioctl dashboard kiali. That command and a plain port-forward are equivalent; "
  "the port-forward was used because it keeps the session independent of the CLI:")
code("""kubectl -n istio-system port-forward svc/kiali 20001:20001 --context kind-mesh1
# http://localhost:20001  ->  Graph  ->  namespace "default\"""")
p("In Kiali: Graph is opened, the default namespace is selected, the microservices are inspected, "
  "the connections between them are observed, and the traffic values confirm that the mesh is "
  "reporting live data.")
fig("21-kiali-service-graph",
    "Step 13 \u2014 Kiali traffic graph for namespace default. Six applications (seven versions), "
    "seven services and twenty edges are reported at 0.73 requests per second with 100% success. "
    "The graph is split into the two clusters: the upper namespace box is mesh1, the lower box is "
    "mesh2, and the edges that cross between them run through the east-west gateways.")

h3("Step 14: Open the Grafana Dashboard")
code("""istioctl dashboard grafana --context kind-mesh1
# or: kubectl -n istio-system port-forward svc/grafana 3000:3000""")
p("The Istio Mesh dashboard is opened. It reports request traffic, request rates, service "
  "performance, latency and error rates.")
fig("22-grafana-mesh-dashboard",
    "Step 14 \u2014 Grafana, Istio Mesh dashboard. Traffic volume 1.60 req/s, success rate 100%, 4xx "
    "and 5xx at zero, and the per-workload request rate and latency table.")

h3("Step 15: Open Prometheus")
code("""istioctl dashboard prometheus --context kind-mesh1
# query: sum by (destination_service_name) (rate(istio_requests_total[1m]))""")
p("Prometheus holds the raw series that Grafana and Kiali read. The query above shows the request "
  "rate per destination service, which is the base signal for almost every Istio dashboard.")
fig("23-prometheus-istio-requests",
    "Step 15 \u2014 Prometheus graph of sum by (destination_service_name) (rate(istio_requests_total[1m])). "
    "One series per destination service, all produced by Envoy sidecars in the two clusters.")

h3("Step 16: Open Jaeger")
code("""istioctl dashboard jaeger --context kind-mesh1
# service list uses the namespaced service name, e.g. productpage.default""")
p("Jaeger receives spans over the zipkin protocol from every proxy that participates in a traced "
  "request. Because the sample Jaeger deployment stores traces in an emptyDir volume, the trace "
  "list is empty after a Jaeger restart until new traffic arrives \u2014 a behaviour worth knowing "
  "when the dashboard appears blank.")
fig("24-jaeger-trace",
    "Step 16 / Step 20 \u2014 Jaeger trace view. The waterfall shows one request entering through "
    "istio-ingressgateway, calling productpage, then details, reviews and finally ratings: four "
    "services, depth seven, eight spans, 18.78 ms end to end.")

# ---- PART D
h2("PART D: Generate Traffic and Observe Service Communication")

h3("Step 17: Generate Application Traffic")
p("Students must generate requests so that the monitoring tools have something to observe. The "
  "gateway address is read from the service object rather than hard-coded:")
code("""GW=$(kubectl -n istio-system get svc istio-ingressgateway --context kind-mesh1 \\
     -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export GATEWAY_URL="$GW:80"

for i in $(seq 1 100); do
  curl -s -o /dev/null "http://$GATEWAY_URL/productpage"
done""")
p("In addition to the 100-request burst, a background loop sends one request per second so that "
  "the dashboards show a continuous line rather than a spike. Every request that reaches the "
  "product page fans out to details, reviews (v1 or v2 by weight) and ratings, so a single ingress "
  "request produces four to eight spans and several metric series.")

h3("Step 18: Observe Traffic in Kiali")
p("Kiali is opened again: Graph, namespace default, the communication between Bookinfo services, "
  "the traffic connections and the services involved in request processing.")
observed("The graph in Figure 21 reports productpage, details, reviews and ratings in both "
         "clusters, with the ingress gateway as the entry point and a steady request rate.")
fref("21-kiali-service-graph",
     "the service graph captured for this step is Figure 21 (Part C). It was taken while the "
     "traffic loop was running, so every edge in it carries the traffic generated here.")

h3("Step 19: Observe Metrics in Grafana")
p("The brief asks to record total requests, request rate, service latency, successful requests and "
  "failed requests wherever the relevant metrics are available. Recorded from the running "
  "dashboard:")
table(
    ["Metric requested by the brief", "Value observed", "Where it is shown"],
    [
        ["Total requests generated", "100 per measurement run, plus 1 req/s continuously", "traffic loop, script 06/08"],
        ["Request rate", "1.60 req/s (dashboard total)", "Grafana, Traffic Volume panel"],
        ["Service latency", "productpage 18.89 ms p50, details 1.67 ms, reviews v1 3.57 ms, reviews v2 17.50 ms, ratings 1.00 ms", "Grafana, HTTP/gRPC Workloads table"],
        ["Successful requests", "100% success rate", "Grafana, Success Rate panel"],
        ["Failed requests", "0 req/s 4xx, 0 req/s 5xx", "Grafana, 4xx and 5xx panels"],
    ],
    widths=[4.6, 7.4, 5.0], small=True)
fref("22-grafana-mesh-dashboard",
     "the dashboard used as the source of these numbers is Figure 22, captured with the same "
     "dashboard, time range and data source.")

h3("Step 20: Observe Distributed Tracing in Jaeger")
p("Jaeger is opened, the relevant service is selected, traces are searched, one trace is opened, "
  "the sequence of service calls is inspected and the duration of each operation is compared.")
observed("A single trace contains eight spans across four services. The ingress gateway span is "
         "18.78 ms; inside it, productpage takes 17.39 ms, details 1.79 ms, reviews 9.05 ms and "
         "ratings 1.53 ms. The nested spans make the call chain explicit: productpage calls details "
         "and reviews in parallel, and reviews calls ratings.")
fref("24-jaeger-trace",
     "the completed trace captured for this step is Figure 24 (Part C): 4 services, depth 7, "
     "8 spans, 18.78 ms.")
note("Note (from the brief)",
     "Trace visibility depends on the sampling configuration and on the number of requests "
     "generated. If traces are not visible immediately, generate additional requests and verify "
     "the tracing configuration \u2014 in this implementation sampling is set to 100% precisely to "
     "remove that uncertainty.")

# ---- PART E
h2("PART E: Test Cross-Cluster Connectivity and Resilience")

h3("Step 21: Verify Cross-Cluster Service Communication")
code("""kubectl get services --context kind-mesh1
kubectl get services --context kind-mesh2""")
p("Cross-cluster discovery was established in Activity 1 Step 13 and is visible in the Envoy "
  "endpoint list (Figure 13). The remaining question is whether requests are actually served by "
  "the other cluster, so sixty requests are sent from a pod in mesh1 and the pod name in each "
  "response is matched against the pod lists of both clusters:")
code("""for i in $(seq 1 60); do
  curl -s http://reviews:9080/reviews/0
  echo
done   # executed inside traffic-client in kind-mesh1""")
observed("routed to mesh1 pods: 32/60, routed to mesh2 pods: 28/60 \u2014 the reviews service is "
         "load balanced across both clusters, which is the required demonstration that a service "
         "in one cluster communicates with its counterpart in the other.")
fig("11-cross-cluster-requests",
    "Step 21 \u2014 live cross-cluster request test. Of 60 requests sent from mesh1, 32 were served by "
    "pods in mesh1 and 28 by pods in mesh2, listed by pod name.")

h3("Step 22: Verify Istio Proxy Health")
code("""istioctl proxy-status --context kind-mesh1
istioctl proxy-status --context kind-mesh2""")
p("The proxy synchronization status is inspected and any proxy that is not synchronized would be "
  "investigated. In this run every proxy reports SYNCED and no proxy is stale.")
fref("09-proxy-status",
     "the full proxy status output for both clusters is Figure 10; the run above was executed "
     "again after the mTLS and routing changes and returned the same result.")

h3("Step 23: Perform a Resilience Test")
p("The objective is to understand what happens when one cluster or service becomes unavailable. "
  "The brief prescribes a controlled test: record the normal response, identify the workload, "
  "scale it down rather than deleting a cluster, send requests again, observe the response and "
  "check the dashboards.")
p("Two tests were performed on reviews-v2, the 20% subset, which exists in both clusters:")
bullets([
    "soft failure: reviews-v2 is scaled to zero in mesh2 only;",
    "hard failure: reviews-v2 is scaled to zero in both clusters.",
])
code("""kubectl scale deployment reviews-v2 --replicas=0 --context kind-mesh2
# ... send requests, observe ...
kubectl scale deployment reviews-v2 --replicas=1 --context kind-mesh2""")
observed("Soft failure: baseline ok=30 fail=0 (v1=25 v2=5); with mesh2's v2 removed ok=30 fail=0 "
         "(v1=24 v2=6) \u2014 no request failed, because the v2 subset still had endpoints in mesh1 and "
         "the mesh rebalanced. Hard failure: ok=25 fail=5 (v1=25 v2=0) while v2 was absent "
         "everywhere, then ok=30 fail=0 after restoring. Five requests failed because the 20% "
         "subset had no destination at all: Istio does not silently reroute a weighted subset to "
         "another version, which is the correct and documented behaviour.")
fig("25-resilience",
    "Step 23 \u2014 resilience test results: soft failure absorbed by the surviving cluster, hard "
    "failure returning 5 failures out of 30 for the empty subset, then full recovery after the "
    "deployment is restored.")
note("Important (from the brief)",
     "Traffic failover is not automatic merely because two clusters are connected. It requires "
     "suitable routing, healthy endpoints, gateway configuration and failover policies. The two "
     "results above show exactly that: losing one cluster's v2 pods is transparent because healthy "
     "endpoints remain in the other cluster, while losing the subset everywhere produces errors "
     "even though the service is still reachable through v1.")

# ---- PART F
h2("PART F: Final Project Verification")

h3("Step 24: Verify All Project Components")
p("The brief lists nine commands to execute and record. They are run in one pass; the output of "
  "the state commands is shown in Figure 27, while proxy status is in Figure 10.")
code("""kubectl get nodes --context kind-mesh1
kubectl get nodes --context kind-mesh2
kubectl get pods -A --context kind-mesh1
kubectl get pods -A --context kind-mesh2
kubectl get peerauthentication --context kind-mesh1
kubectl get virtualservice --context kind-mesh1
kubectl get destinationrule --context kind-mesh1
istioctl proxy-status --context kind-mesh1
istioctl proxy-status --context kind-mesh2""")
fig("26-final-verification",
    "Step 24 \u2014 final verification pass: both nodes Ready, all Bookinfo pods 2/2 Running, "
    "PeerAuthentication STRICT, the bookinfo and reviews VirtualServices and the reviews "
    "DestinationRule all present.")

h3("Step 25: Prepare the Final Project Report")
p("The report you are reading is that deliverable. Its fourteen required items are listed at the "
  "front of this document with the section and figure that covers each one.")

h3("Step 26: Submit the Required Evidence")
table(
    ["#", "Evidence required by the brief", "Where it is shown"],
    [
        ["1", "Both Kubernetes clusters and their nodes", "Figures 3 and 4"],
        ["2", "Istio installation", "Figures 6 and 7"],
        ["3", "Cross-cluster connectivity configuration", "Figures 8, 9, 13 and 25"],
        ["4", "Bookinfo microservices deployment", "Figure 11"],
        ["5", "Envoy sidecar injection", "Figure 12"],
        ["6", "PeerAuthentication configuration", "Figure 14 (and 15 for enforcement)"],
        ["7", "VirtualService and DestinationRule configuration", "Figures 16, 17 and 18"],
        ["8", "Kiali service graph", "Figure 21"],
        ["9", "Grafana monitoring dashboard", "Figure 22"],
        ["10", "Prometheus metrics", "Figure 23"],
        ["11", "Jaeger distributed tracing", "Figure 24"],
        ["12", "Proxy status", "Figure 10"],
        ["13", "Resilience test results", "Figure 26"],
    ],
    widths=[1.0, 9.6, 6.4], small=True)

h2("Expected Outcome of Activity 2")
p("At the end of this activity the implementation has:")
bullets([
    "strict mTLS for service-to-service security, enforced and proven with a plaintext client;",
    "traffic routing between microservice versions, configured 80:20 and measured at 79:21;",
    "Prometheus and Grafana installed and reporting request rate, latency and errors;",
    "Kiali integrated and showing the live service graph across both clusters;",
    "Jaeger integrated and showing complete request traces;",
    "application traffic generated and analysed;",
    "cross-cluster service communication tested with requests served by both clusters;",
    "a controlled resilience test performed and explained;",
    "the final project report prepared.",
])
lead("Activity 2 deliverable",
     "A secured, monitored and tested multi-cloud service mesh with traffic management and "
     "observability capabilities.")

# --------------------------------------------------------------------------- #
#  final checklist
# --------------------------------------------------------------------------- #
brk()
h1("Final Project Completion Checklist")
p("Students are considered to have completed the project when both activities are finished and "
  "the required evidence has been submitted. The status column records the evidence produced by "
  "this implementation.")
table(
    ["No.", "Project requirement", "Activity", "Status", "Evidence"],
    [
        ["1", "Create AWS EKS cluster", "Activity 1", "Done (local equivalent)", "Figure 3"],
        ["2", "Create Google Cloud GKE cluster", "Activity 1", "Done (local equivalent)", "Figure 4"],
        ["3", "Install and configure Istio", "Activity 1", "Done", "Figures 6, 7, 10"],
        ["4", "Configure cross-cluster communication", "Activity 1", "Done", "Figures 8, 9, 13"],
        ["5", "Deploy Bookinfo microservices", "Activity 1", "Done", "Figure 11"],
        ["6", "Verify Envoy sidecar injection", "Activity 1", "Done", "Figure 12"],
        ["7", "Implement mutual TLS", "Activity 2", "Done", "Figures 14, 15"],
        ["8", "Configure VirtualService", "Activity 2", "Done", "Figure 16"],
        ["9", "Configure DestinationRule", "Activity 2", "Done", "Figure 17"],
        ["10", "Install Prometheus and Grafana", "Activity 2", "Done", "Figures 19, 20, 22, 23"],
        ["11", "Configure Kiali", "Activity 2", "Done", "Figure 21"],
        ["12", "Configure Jaeger", "Activity 2", "Done", "Figure 24"],
        ["13", "Generate and monitor application traffic", "Activity 2", "Done", "Figures 18, 22"],
        ["14", "Test cross-cluster connectivity", "Activity 2", "Done", "Figures 11, 13, 25"],
        ["15", "Perform resilience testing", "Activity 2", "Done", "Figure 26"],
        ["16", "Prepare and submit the final project report", "Activity 2", "Done", "This document"],
    ],
    widths=[0.9, 6.0, 2.0, 4.0, 4.1], small=True)

h1("Final Submission Requirements")
p("The brief asks for six items. This submission contains all of them:")
table(
    ["#", "Required", "Where it is"],
    [
        ["1", "Completed Activity 1 implementation", "Activity 1, Sections 6 (Parts A\u2013F)"],
        ["2", "Completed Activity 2 implementation", "Activity 2 (Parts A\u2013F)"],
        ["3", "YAML configuration files", "Appendix A, plus the yaml/ directory"],
        ["4", "Relevant terminal command outputs", "Every step, plus evidence/*.txt"],
        ["5", "Screenshots of all major implementation stages", "27 figures, captured from the running system"],
        ["6", "Final project report", "This document"],
    ],
    widths=[1.0, 9.0, 7.0], small=True)

h1("Project Completion Criteria")
p("The project is complete when both activities have been implemented, the required "
  "configurations and tests have been verified, and all submission materials have been provided. "
  "Every configuration in this report was applied to a live mesh, every test was executed against "
  "it, and every screenshot was taken from that running system.")
note("Important implementation note (from the brief)",
     "This project uses two independently managed platforms. Creating two Kubernetes clusters does "
     "not automatically connect them. Cross-cloud networking, gateway reachability, Istio cluster "
     "topology, service discovery and certificate trust must all be configured and verified. A "
     "successful installation command alone is not sufficient evidence of project completion \u2014 "
     "which is why this report shows the Envoy endpoint list, the measured cross-cluster request "
     "split, the enforced mTLS rejection and the failure behaviour of an empty subset.")

# --------------------------------------------------------------------------- #
#  challenges and conclusion
# --------------------------------------------------------------------------- #
h1("12. Challenges Faced and Solutions")
p("The problems below were met while building the environment; each one changed the implementation "
  "or the scripts that reproduce it.")
table(
    ["Challenge", "Symptom", "Root cause and solution"],
    [
        ["Cross-cluster 503s after the shared CA was installed",
         "Every ingress request returned 503 and cross-cluster calls failed the TLS handshake.",
         "Proxies that started before the cacerts secret kept certificates from the previous CA. "
         "Solution: restart istiod, both gateways and the workloads after installing cacerts "
         "(script 03b-shared-ca.sh)."],
        ["Remote cluster status 'timeout' after a host reboot",
         "Cross-cluster load balancing silently stopped; only local endpoints were returned.",
         "Docker reassigned the bridge addresses, so each remote secret pointed at the wrong node "
         "(usually its own). Solution: reconcile both secrets against the current node IPs at the "
         "end of 03-istio-multicluster.sh."],
        ["Jaeger showed no traces",
         "The Jaeger UI was reachable but the service list was empty.",
         "Two independent causes: no extension provider in meshConfig, so Envoy had nowhere to "
         "send spans, and no Telemetry resource, so tracing was off. Solution: add the zipkin "
         "provider to the operator manifest and apply Telemetry/mesh-default with 100% sampling."],
        ["Jaeger UI returned 404 at the root path",
         "The dashboard was mounted under /jaeger while its router expected /.",
         "The sample manifest sets base_path: /jaeger. Solution: patch the config map to base_path: / "
         "and restart the deployment."],
        ["Ambiguous sidecar evidence",
         "kubectl get pods showed 2/2 but .spec.containers listed only the application container.",
         "Istio 1.32 uses native sidecars, which appear as initContainers with restartPolicy: "
         "Always. Solution: document the initContainers column explicitly (Figure 12)."],
        ["Traffic split not visible in a short sample",
         "A 20-request sample sometimes showed 15:5 or 17:3, which looks like a wrong weight.",
         "Weighted routing is probabilistic per request. Solution: measure over 100 requests and "
         "report the count, not the percentage of a small sample."],
        ["Weighted subset empty during the resilience test",
         "Five requests out of thirty returned errors while reviews-v2 was scaled to zero.",
         "A VirtualService route to an empty subset has no destination; Istio does not silently "
         "fall back to another version. Solution: keep the behaviour, explain it, and show that "
         "losing only one cluster's copy is transparent."],
        ["Long shell commands timing out at the Windows/WSL boundary",
         "wsl invocations intermittently failed with Wsl/Service/0x8007274c while the VM stayed up.",
         "Interop timeout, not a crash. Solution: run long scripts detached and poll the log file, "
         "or retry the same command."],
    ],
    widths=[4.6, 5.2, 7.4], small=True)

h1("13. Conclusion")
p("The project delivered a two-cluster Istio service mesh in which the security, traffic "
  "management and observability requirements of the brief are all demonstrated on live traffic.")
p("Both clusters run their own control plane and communicate through east-west gateways, so the "
  "mesh keeps working when one side is degraded. Mutual TLS is enforced in STRICT mode and the "
  "rejection of a plaintext client is captured as evidence, not asserted. The 80:20 split between "
  "reviews v1 and v2 was configured declaratively and then measured at 79:21 across 100 requests. "
  "Cross-cluster discovery is visible in Envoy's endpoint list as the peer gateway on port 15443, "
  "and 28 of 60 requests from one cluster were served by pods in the other. Prometheus, Grafana, "
  "Kiali and Jaeger report the same traffic from four different angles: metrics, dashboards, a "
  "service graph and end-to-end traces.")
p("The resilience test completes the picture: losing one cluster's copy of a subset is absorbed "
  "without a single failed request, while removing the subset everywhere produces the errors that "
  "the routing model predicts. That difference is the practical lesson of the project \u2014 "
  "connectivity is not failover, and a mesh only does what its policies say.")
p("Running the two clusters locally instead of on EKS and GKE changed the provider, not the "
  "problem: separate control planes, isolated pod networks, load-balanced gateways, a shared root "
  "of trust and cross-cluster SNI routing are all present, and every command needed to rebuild the "
  "environment is in Appendix C.")

# --------------------------------------------------------------------------- #
#  appendices
# --------------------------------------------------------------------------- #
brk()
h1("Appendix A: YAML Configuration Files")
p("The three manifests required by Activity 2, reproduced exactly as applied.")

h2("A.1  peer-authentication.yaml")
code(open(os.path.join(ROOT, "yaml", "peer-authentication.yaml"), encoding="utf-8").read())

h2("A.2  reviews-destination-rule.yaml")
code(open(os.path.join(ROOT, "yaml", "reviews-destination-rule.yaml"), encoding="utf-8").read())

h2("A.3  reviews-virtual-service.yaml")
code(open(os.path.join(ROOT, "yaml", "reviews-virtual-service.yaml"), encoding="utf-8").read())

h2("A.4  Telemetry resource (tracing)")
code("""apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
  name: mesh-default
  namespace: istio-system
spec:
  tracing:
    - providers:
        - name: jaeger
      randomSamplingPercentage: 100.0""")

h1("Appendix B: Evidence Inventory")
p("The raw text of every terminal screenshot is kept next to the screenshots, so the numbers in "
  "this report can be checked without re-running anything.")
table(
    ["File", "Contents"],
    [
        ["evidence/verify-20261113-142220.txt", "Full verification run: nodes, all pods, policies, proxies, endpoints, cross-cluster request test, ingress check"],
        ["evidence/resilience-20261112-165649.txt", "Soft and hard resilience runs with the restore steps"],
        ["evidence/doc-screens.html", "Terminal-rendered cards used for the figures (view with ?s=NN)"],
        ["evidence/architecture.html", "Source of Figure 1"],
        ["screenshots/00-architecture.png", "Architecture diagram"],
        ["screenshots/01..12, 14..20, 25..26", "Terminal evidence cards, one per step"],
        ["screenshots/21-kiali-service-graph.png", "Kiali traffic graph"],
        ["screenshots/22-grafana-mesh-dashboard.png", "Grafana Istio Mesh dashboard"],
        ["screenshots/23-prometheus-istio-requests.png", "Prometheus request-rate query"],
        ["screenshots/24-jaeger-trace.png", "Jaeger trace waterfall"],
    ],
    widths=[6.4, 10.6], small=True)

h1("Appendix C: Reproducing the Implementation")
p("The environment is rebuilt from the scripts in scripts/. They are idempotent and stop at the "
  "first failure.")
table(
    ["Script", "Purpose"],
    [
        ["01-wsl-preflight.sh", "Checks the host: WSL2, Docker, memory, disk"],
        ["02-clusters-up.sh", "Creates kind clusters mesh1 (10.244/16) and mesh2 (10.245/16), joins them to mesh-underlay, installs MetalLB"],
        ["03-istio-multicluster.sh", "Installs istiod and both gateways per cluster, exposes services, exchanges and reconciles the remote secrets"],
        ["03b-shared-ca.sh", "Installs the shared root CA and restarts istiod, gateways and workloads"],
        ["04-bookinfo.sh", "Deploys Bookinfo in both clusters plus the ingress gateway and the test clients"],
        ["05-mtls.sh", "Applies PeerAuthentication STRICT in both clusters"],
        ["06-traffic-routing.sh", "Applies DestinationRule and VirtualService, measures the 80:20 split over 100 requests"],
        ["07-addons.sh", "Installs Prometheus, Grafana, Kiali and Jaeger, enables tracing, fixes the Jaeger base path"],
        ["08-generate-traffic.sh", "Generates the request burst used by the dashboards"],
        ["09-verify.sh", "Writes evidence/verify-*.txt with the full verification pass"],
        ["10-resilience.sh", "Soft failure by default; --hard removes the subset from both clusters"],
        ["11-dashboards.sh", "Port-forwards Kiali 20001, Grafana 3000, Prometheus 9090, Jaeger 16686"],
        ["12-traffic-loop.sh", "One request per second through the ingress gateway"],
        ["14-doc-screens.sh", "Captures the terminal cards rendered as figures in this report"],
        ["99-teardown.sh", "Deletes both kind clusters"],
    ],
    widths=[5.2, 11.8], small=True)
code("""git clone <repository>
cd devops-project-5
bash scripts/02-clusters-up.sh
bash scripts/03-istio-multicluster.sh
bash scripts/03b-shared-ca.sh
bash scripts/04-bookinfo.sh
bash scripts/05-mtls.sh
bash scripts/06-traffic-routing.sh
bash scripts/07-addons.sh
bash scripts/09-verify.sh
bash scripts/10-resilience.sh
bash scripts/11-dashboards.sh
bash scripts/14-doc-screens.sh""")
p("The full rebuild takes about twenty minutes on a machine with 8 GB of RAM and four cores. "
  "Teardown is a single command: bash scripts/99-teardown.sh.")

# --------------------------------------------------------------------------- #
#  renderer
# --------------------------------------------------------------------------- #
FIGFILES = {}
for name in sorted(os.listdir(SHOTS)):
    if name.lower().endswith(".png"):
        FIGFILES[name[:-4]] = name

FIGNUMS = {}
n = 0
for blk in B:
    if blk[0] == "fig":
        n += 1
        FIGNUMS[blk[1]] = n

# PNG pixel dimensions -> document height, so tall cards still fit a page
import struct


def png_size(path):
    """Read width/height straight from the PNG IHDR chunk (no dependencies)."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return (1200, 600)
        return struct.unpack(">II", head[16:24])
    except Exception:
        return (1200, 600)


# ---- document setup -------------------------------------------------------- #
doc = Document()

sec = doc.sections[0]
sec.page_width = Cm(21.0)
sec.page_height = Cm(29.7)
sec.top_margin = Cm(2.0)
sec.bottom_margin = Cm(2.0)
sec.left_margin = Cm(2.1)
sec.right_margin = Cm(2.1)
sec.header_distance = Cm(1.0)
sec.footer_distance = Cm(1.0)

styles = doc.styles
normal = styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(BODY_PT)
normal.font.color.rgb = DARK
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.12
rpr = normal.element.get_or_add_rPr()
rf = rpr.find(qn("w:rFonts"))
if rf is None:
    rf = OxmlElement("w:rFonts")
    rpr.append(rf)
rf.set(qn("w:eastAsia"), "Calibri")

for name, size, colour, before, after in (
        ("Heading 1", 15, NAVY, 16, 6),
        ("Heading 2", 12.5, BLUE, 13, 4),
        ("Heading 3", 11, NAVY, 10, 3)):
    st = styles[name]
    st.font.name = "Calibri"
    st.font.size = Pt(size)
    st.font.bold = True
    st.font.color.rgb = colour
    st.paragraph_format.space_before = Pt(before)
    st.paragraph_format.space_after = Pt(after)
    st.paragraph_format.keep_with_next = True


def shade(paragraph, fill):
    pPr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pPr.append(shd)


def border(paragraph, colour="D0D7E2", size=6, sides=("top", "left", "bottom", "right")):
    pPr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    for side in sides:
        el = OxmlElement("w:" + side)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:space"), "4")
        el.set(qn("w:color"), colour)
        pbdr.append(el)
    pPr.append(pbdr)


def cell_shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def add_page_number(paragraph):
    run = paragraph.add_run()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run._r.addnext(fld)


def set_cell_margins(table, top=60, bottom=60, left=90, right=90):
    tblPr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement("w:" + side)
        el.set(qn("w:w"), str(value))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def twips(cm_value):
    return int(round(cm_value * 567))


def fix_table_grid(table, widths_cm):
    """Force a fixed layout with explicit column widths.

    Setting cell.width alone is only a suggestion: Word and LibreOffice both
    fall back to the tblGrid, so the grid, the table width and the layout mode
    all have to agree or the columns come out evenly spaced.
    """
    tbl = table._tbl
    tblPr = tbl.tblPr
    total = twips(sum(widths_cm))

    for tag in ("w:tblW", "w:tblLayout"):
        old = tblPr.find(qn(tag))
        if old is not None:
            tblPr.remove(old)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), str(total))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)

    grid = tbl.find(qn("w:tblGrid"))
    if grid is not None:
        for gc in list(grid):
            grid.remove(gc)
        for w in widths_cm:
            gc = OxmlElement("w:gridCol")
            gc.set(qn("w:w"), str(twips(w)))
            grid.append(gc)

    for row in table.rows:
        for cell, w in zip(row.cells, widths_cm):
            cell.width = Cm(w)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def no_row_split(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trPr.append(el)


# ---- header / footer ------------------------------------------------------- #
hdr = sec.header.paragraphs[0]
hdr.text = "DevOps Project 5 \u2014 Multi-Cloud Service Mesh Implementation"
hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
for r in hdr.runs:
    r.font.size = Pt(8)
    r.font.color.rgb = GREY
hdr.paragraph_format.space_after = Pt(0)
border(hdr, colour="BFC9D9", size=4, sides=("bottom",))

ftr = sec.footer.paragraphs[0]
ftr.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = ftr.add_run("Page ")
r.font.size = Pt(8)
r.font.color.rgb = GREY
add_page_number(ftr)
for r in ftr.runs:
    r.font.size = Pt(8)
    r.font.color.rgb = GREY

# ---- cover ----------------------------------------------------------------- #
for _ in range(2):
    doc.add_paragraph()

p_title = doc.add_paragraph()
p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p_title.add_run("DEVOPS PROJECT 5")
run.font.size = Pt(30)
run.font.bold = True
run.font.color.rgb = NAVY

p_sub = doc.add_paragraph()
p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p_sub.add_run("MULTI-CLOUD SERVICE MESH IMPLEMENTATION")
run.font.size = Pt(17)
run.font.bold = True
run.font.color.rgb = BLUE
p_sub.paragraph_format.space_after = Pt(2)

p_sub2 = doc.add_paragraph()
p_sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p_sub2.add_run("Activity 1 \u00b7 Activity 2 \u2014 implementation report with captured evidence")
run.font.size = Pt(11)
run.font.color.rgb = GREY
p_sub2.paragraph_format.space_after = Pt(22)

rule = doc.add_paragraph()
border(rule, colour="1F3864", size=12, sides=("top",))

meta = doc.add_table(rows=0, cols=2)
meta.alignment = WD_TABLE_ALIGNMENT.CENTER
rows = [
    ("Student", "______________________________________"),
    ("Roll number", "______________________________________"),
    ("Course", "DevOps \u2014 Project 5"),
    ("Submitted", "13 November 2026"),
    ("Environment", "Ubuntu 24.04 LTS on WSL2, Docker 29.1.3, kind v0.34.0, Kubernetes v1.37.0, Istio 1.32.0"),
    ("Clusters", "kind-mesh1 (stands in for AWS EKS) and kind-mesh2 (stands in for Google GKE)"),
]
for a, b in rows:
    cells = meta.add_row().cells
    cells[0].width = Cm(3.6)
    cells[1].width = Cm(12.4)
    pr = cells[0].paragraphs[0]
    r = pr.add_run(a)
    r.font.bold = True
    r.font.size = Pt(9.5)
    r.font.color.rgb = NAVY
    pr.paragraph_format.space_after = Pt(2)
    pv = cells[1].paragraphs[0]
    r = pv.add_run(b)
    r.font.size = Pt(9.5)
    pv.paragraph_format.space_after = Pt(2)
set_cell_margins(meta, top=30, bottom=30)
fix_table_grid(meta, [3.6, 12.4])

spacer = doc.add_paragraph()
spacer.paragraph_format.space_after = Pt(18)

box = doc.add_paragraph()
shade(box, "EEF3FA")
border(box, colour="9DB9D8", size=8)
box.paragraph_format.left_indent = Cm(0.2)
box.paragraph_format.right_indent = Cm(0.2)
box.paragraph_format.space_before = Pt(6)
box.paragraph_format.space_after = Pt(6)
r = box.add_run("Implementation note  ")
r.font.bold = True
r.font.size = Pt(9.5)
r.font.color.rgb = NAVY
r = box.add_run(
    "The brief describes AWS EKS and Google Cloud GKE. This implementation reaches the same "
    "topology with two kind clusters on one host: separate API servers, separate pod networks, "
    "load-balanced gateways on a shared underlay, one Istio mesh with a shared root of trust, and "
    "real evidence at every step. No cloud account was used and no cloud charges were incurred. "
    "Section 5 records the substitution item by item.")
r.font.size = Pt(9.5)

doc.add_page_break()

# ---- body ------------------------------------------------------------------ #
in_cover_done = True


def add_code_par(text):
    par = doc.add_paragraph()
    par.paragraph_format.space_before = Pt(4)
    par.paragraph_format.space_after = Pt(8)
    par.paragraph_format.left_indent = Cm(0.25)
    par.paragraph_format.right_indent = Cm(0.1)
    par.paragraph_format.line_spacing = 1.0
    shade(par, "F4F6F9")
    border(par, colour="C9D3E0", size=6)
    lines = text.rstrip("\n").split("\n")
    for i, line in enumerate(lines):
        run = par.add_run(line)
        run.font.name = "Consolas"
        run.font.size = Pt(CODE_PT)
        run.font.color.rgb = RGBColor(0x1B, 0x27, 0x33)
        if i < len(lines) - 1:
            run.add_break()


def add_figure(key, caption):
    path = os.path.join(SHOTS, FIGFILES[key])
    num = FIGNUMS[key]
    w, h = png_size(path)
    width_cm = 16.6 if w >= 1100 else 15.0
    # keep the rendered height inside the text area
    max_h_cm = 19.0
    height_cm = width_cm * h / w
    if height_cm > max_h_cm:
        width_cm = max_h_cm * w / h
    pic_par = doc.add_paragraph()
    pic_par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pic_par.paragraph_format.space_before = Pt(8)
    pic_par.paragraph_format.space_after = Pt(3)
    pic_par.paragraph_format.keep_with_next = True
    pic_par.add_run().add_picture(path, width=Cm(width_cm))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(12)
    r = cap.add_run("Figure %d. " % num)
    r.font.bold = True
    r.font.size = Pt(8.5)
    r.font.color.rgb = NAVY
    r = cap.add_run(caption)
    r.font.size = Pt(8.5)
    r.font.italic = True
    r.font.color.rgb = GREY


for blk in B:
    kind = blk[0]

    if kind == "cover":
        continue

    if kind == "brk":
        doc.add_page_break()
        continue

    if kind == "h1":
        doc.add_heading(blk[1], level=1)
        continue

    if kind == "h2":
        doc.add_heading(blk[1], level=2)
        continue

    if kind == "h3":
        doc.add_heading(blk[1], level=3)
        continue

    if kind == "p":
        opts = blk[2]
        par = doc.add_paragraph(blk[1])
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if opts.get("italic"):
            for r in par.runs:
                r.font.italic = True
        continue

    if kind == "lead":
        par = doc.add_paragraph()
        par.paragraph_format.space_before = Pt(4)
        r = par.add_run(blk[1] + ":  ")
        r.font.bold = True
        r.font.color.rgb = NAVY
        par.add_run(blk[2])
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        continue

    if kind in ("bullets", "numbered"):
        style = "List Bullet" if kind == "bullets" else "List Number"
        for item in blk[1]:
            par = doc.add_paragraph(item, style=style)
            par.paragraph_format.space_after = Pt(3)
            par.paragraph_format.line_spacing = 1.08
        continue

    if kind == "code":
        add_code_par(blk[1])
        continue

    if kind == "expected":
        par = doc.add_paragraph()
        par.paragraph_format.left_indent = Cm(0.25)
        r = par.add_run("Expected Result:  ")
        r.font.bold = True
        r.font.color.rgb = NAVY
        r = par.add_run(blk[1])
        r.font.italic = True
        continue

    if kind == "observed":
        par = doc.add_paragraph()
        par.paragraph_format.left_indent = Cm(0.25)
        par.paragraph_format.space_after = Pt(6)
        r = par.add_run("\u2713  Observed:  ")
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x2F, 0x6F, 0x4F)
        r = par.add_run(blk[1])
        continue

    if kind == "note":
        par = doc.add_paragraph()
        shade(par, "FFF7E6")
        border(par, colour="E0B979", size=8)
        par.paragraph_format.left_indent = Cm(0.2)
        par.paragraph_format.right_indent = Cm(0.2)
        par.paragraph_format.space_before = Pt(6)
        par.paragraph_format.space_after = Pt(9)
        r = par.add_run(blk[1] + ".  ")
        r.font.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0x7A, 0x4E, 0x10)
        r = par.add_run(blk[2])
        r.font.size = Pt(9.5)
        continue

    if kind == "table":
        headers, rows, widths, small = blk[1], blk[2], blk[3], blk[4]
        if widths:
            total = sum(widths)
            if total > 16.6:
                widths = [w * 16.6 / total for w in widths]
        tbl = doc.add_table(rows=1, cols=len(headers))
        tbl.style = "Table Grid"
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False
        set_cell_margins(tbl)
        hdr_cells = tbl.rows[0].cells
        for i, text in enumerate(headers):
            if widths:
                hdr_cells[i].width = Cm(widths[i])
            cell_shade(hdr_cells[i], "1F3864")
            par = hdr_cells[i].paragraphs[0]
            par.paragraph_format.space_after = Pt(0)
            r = par.add_run(text)
            r.font.bold = True
            r.font.size = Pt(8.5 if small else 9)
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        for ri, row in enumerate(rows):
            cells = tbl.add_row().cells
            for i, text in enumerate(row):
                if widths:
                    cells[i].width = Cm(widths[i])
                if ri % 2 == 1:
                    cell_shade(cells[i], "F2F5F9")
                par = cells[i].paragraphs[0]
                par.paragraph_format.space_after = Pt(0)
                par.paragraph_format.line_spacing = 1.0
                r = par.add_run(str(text))
                r.font.size = Pt(8.5 if small else 9)
        if widths:
            fix_table_grid(tbl, widths)
        repeat_header(tbl.rows[0])
        for row in tbl.rows:
            no_row_split(row)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
        continue

    if kind == "fig":
        add_figure(blk[1], blk[2])
        continue

    if kind == "fref":
        num = FIGNUMS[blk[1]]
        par = doc.add_paragraph()
        shade(par, "F1F5FA")
        border(par, colour="C9D3E0", size=6)
        par.paragraph_format.left_indent = Cm(0.2)
        par.paragraph_format.right_indent = Cm(0.2)
        par.paragraph_format.space_before = Pt(6)
        par.paragraph_format.space_after = Pt(9)
        r = par.add_run("Evidence \u2014 Figure %d. " % num)
        r.font.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = NAVY
        r = par.add_run(blk[2])
        r.font.size = Pt(9.5)
        r.font.italic = True
        continue

    if kind == "quote":
        par = doc.add_paragraph(blk[1])
        par.paragraph_format.left_indent = Cm(0.8)
        par.paragraph_format.right_indent = Cm(0.8)
        for r in par.runs:
            r.font.italic = True
            r.font.color.rgb = GREY
        continue

os.makedirs(os.path.dirname(OUT), exist_ok=True)
doc.save(OUT)
print("wrote", OUT)
print("figures:", len(FIGNUMS))
print("paragraphs:", len(doc.paragraphs))
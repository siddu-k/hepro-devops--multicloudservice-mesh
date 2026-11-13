#!/usr/bin/env python3
"""
add_screenshots_to_pdf.py

Insert the captured screenshots into the ORIGINAL project brief
    DEVOPS PROJECT 5 Activities.pdf
without rebuilding or rewriting it.

Every original page is copied unchanged. A screenshot page is inserted
immediately after the page that contains the step asking for that evidence,
so the figures appear at the section they belong to.

Output: "DEVOPS PROJECT 5 Activities - with screenshots.pdf"
"""

import os

import pymupdf

DOWNLOADS = "/mnt/c/Users/srida/Downloads"
SRC = os.path.join(DOWNLOADS, "DEVOPS PROJECT 5 Activities.pdf")
OUT = os.path.join(DOWNLOADS, "DEVOPS PROJECT 5 Activities - with screenshots.pdf")
SHOTS = "/mnt/c/siddu/VOICE DESK/devops-project-5/screenshots"

FONT_DIR = "/usr/share/fonts/truetype/crosextra"
F_REG = os.path.join(FONT_DIR, "Carlito-Regular.ttf")
F_BOLD = os.path.join(FONT_DIR, "Carlito-Bold.ttf")
F_ITAL = os.path.join(FONT_DIR, "Carlito-Italic.ttf")

NAVY = (0x1F / 255, 0x38 / 255, 0x64 / 255)
BLUE = (0x2E / 255, 0x54 / 255, 0x8C / 255)
GREY = (0x59 / 255, 0x5F / 255, 0x69 / 255)
RULE = (0xC9 / 255, 0xD3 / 255, 0xE0 / 255)

# --------------------------------------------------------------------------- #
#  what goes where
#  anchor = 1-based page of the original document; the screenshots are added
#  directly after that page, in the order listed.
# --------------------------------------------------------------------------- #
PLAN = {
    1: [
        ("00-architecture", "Project architecture",
         "The implemented topology: two independent kind clusters joined into one Istio mesh "
         "through east-west gateways, with a shared root of trust."),
    ],
    2: [
        ("01-tool-versions", "Step 2: Check the Installed Tools",
         "kubectl v1.37.1, istioctl 1.32.0, kind v0.34.0 and Docker 29.1.3, as installed in the "
         "Ubuntu environment used for the whole project."),
    ],
    4: [
        ("02-nodes-mesh1", "Step 6: Verify the AWS Cluster",
         "Cluster 1 (mesh1). The node is Ready, Kubernetes v1.37.0, internal address "
         "172.30.0.3 on the shared underlay network."),
        ("03-nodes-mesh2", "Step 7: Create a GKE Cluster",
         "Cluster 2 (mesh2). A separate API server and a separate node, pod CIDR 10.245.0.0/16, "
         "internal address 172.30.0.2."),
        ("04-kubectl-contexts", "Step 8: Connect kubectl to the GKE Cluster",
         "Both kubectl contexts are present. kind-mesh1 stands in for EKS and kind-mesh2 for GKE; "
         "kind-mesh2 is the current context."),
    ],
    6: [
        ("05-istio-pods-mesh1", "Step 11: Install Istio in the Primary Cluster",
         "istiod, istio-ingressgateway and istio-eastwestgateway running in cluster 1 (mesh1)."),
        ("12-remote-clusters", "Step 13: Configure the GKE Cluster as a Remote Cluster",
         "Remote cluster registration: mesh2 is synced into mesh1's control plane and mesh1 into "
         "mesh2's, which is what makes cross-cluster service discovery work."),
        ("13-gateway-vips", "Step 13: Configure the GKE Cluster as a Remote Cluster",
         "Gateway addresses in both clusters: ingress 172.30.0.200 / 172.30.0.210 on port 80, "
         "east-west 172.30.0.201 / 172.30.0.211 on port 15443."),
    ],
    7: [
        ("06-istio-pods-mesh2", "Step 14: Verify the Istio Installation",
         "The same components in cluster 2 (mesh2): istiod and both gateways are running."),
    ],
    8: [
        ("07-bookinfo-pods", "Step 16: Check the Application Pods",
         "Bookinfo pods in cluster 1, each 2/2 Running (application container plus Envoy sidecar). "
         "traffic-client is the in-mesh client, mtls-probe is deliberately without a sidecar."),
        ("08-sidecar-injection", "Step 17: Verify Envoy Sidecar Injection",
         "Every workload carries istio-init and istio-proxy; the mtls-probe pod has none."),
        ("09-proxy-status", "Step 18: Check Istio Service Information",
         "istioctl proxy-status for both clusters. Every proxy is synchronised with its own istiod: "
         "CDS, LDS, EDS and RDS are all subscribed."),
        ("10-cross-cluster-endpoints", "Step 19: Record the Results",
         "Cross-cluster service discovery. Envoy lists the three local reviews pods and, as a "
         "fourth endpoint, mesh2's east-west gateway 172.30.0.211:15443."),
    ],
    10: [
        ("14-peerauthentication", "Step 4: Verify the mTLS Policy",
         "The PeerAuthentication object as returned by the API server, with spec.mtls.mode: STRICT."),
        ("15-mtls-test", "Step 4: Verify the mTLS Policy",
         "Enforcement test. The in-mesh client gets HTTP 200 through the encrypted tunnel; the same "
         "request from a pod without a sidecar is reset (HTTP 000, curl exit 56)."),
    ],
    12: [
        ("17-destinationrule", "Step 6: Create a DestinationRule",
         "DestinationRule reviews: the v1, v2 and v3 subsets selected by the version pod label."),
        ("16-virtualservice", "Step 8: Create a VirtualService",
         "VirtualService reviews as returned by the API server: 80% to subset v1, 20% to subset v2."),
        ("18-traffic-split", "Step 10: Verify the Traffic Rules",
         "Measured split over 100 requests: v1=79, v2=21, v3=0, fail=0. The 80:20 weight is applied "
         "by the proxy, not merely stored in the configuration."),
    ],
    13: [
        ("19-observability-pods", "Step 12: Verify the Monitoring Components",
         "Prometheus, Grafana, Kiali and Jaeger pods running in istio-system."),
        ("20-observability-services", "Step 12: Verify the Monitoring Components",
         "The service objects behind the dashboards: grafana 3000, kiali 20001/9090, prometheus "
         "9090, jaeger-collector 9411/14268/14250 and tracing 80/16685."),
        ("21-kiali-service-graph", "Step 13: Open the Kiali Dashboard",
         "Kiali traffic graph for namespace default: seven services and twenty edges at 0.73 "
         "requests per second with 100% success. The upper box is mesh1, the lower box is mesh2, "
         "and the edges between them run through the east-west gateways."),
    ],
    14: [
        ("22-grafana-mesh-dashboard", "Step 14: Open the Grafana Dashboard",
         "Grafana, Istio Mesh dashboard: 1.60 req/s, 100% success, zero 4xx and 5xx, and the "
         "per-workload request rate and latency table."),
        ("23-prometheus-istio-requests", "Step 15: Open Prometheus",
         "Prometheus graph of sum by (destination_service_name) (rate(istio_requests_total[1m])): "
         "one series per destination service, all produced by the Envoy sidecars."),
        ("24-jaeger-trace", "Step 16: Open Jaeger",
         "A completed trace: 4 services, depth 7, 8 spans, 18.78 ms end to end, from the ingress "
         "gateway through productpage, details, reviews and ratings."),
    ],
    16: [
        ("11-cross-cluster-requests", "Step 21: Verify Cross-Cluster Service Communication",
         "Live cross-cluster request test. Of 60 requests sent from mesh1, 32 were served by pods in "
         "mesh1 and 28 by pods in mesh2."),
    ],
    17: [
        ("25-resilience", "Step 23: Perform a Resilience Test",
         "Soft failure (reviews-v2 removed from mesh2 only) is absorbed without a failed request; "
         "hard failure (removed everywhere) returns 5 failures out of 30 for the empty subset, then "
         "recovers after the deployment is restored."),
        ("26-final-verification", "Step 24: Verify All Project Components",
         "Final verification pass: both nodes Ready, all Bookinfo pods 2/2 Running, "
         "PeerAuthentication STRICT, the VirtualServices and the DestinationRule all present."),
    ],
}

MAX_W = 505.0          # usable width between the margins
MARGIN_X = 45.0
TOP = 58.0
BOTTOM = 60.0
PAGE_H = 841.92
PAGE_W = 595.32


FONT_REG = pymupdf.Font(fontfile=F_REG)
FONT_BOLD = pymupdf.Font(fontfile=F_BOLD)
FONT_ITAL = pymupdf.Font(fontfile=F_ITAL)


def wrap_with_prefix(prefix, text, size, width):
    """Wrap a caption whose first line starts with a bold 'Screenshot N. ' label."""
    lines = []
    words = text.split()
    first = True
    cur = ""
    while words:
        w = words.pop(0)
        avail = width - (FONT_BOLD.text_length(prefix, fontsize=size) if first else 0.0)
        trial = (cur + " " + w).strip()
        if FONT_REG.text_length(trial, fontsize=size) <= avail:
            cur = trial
        elif cur:
            lines.append((first, cur))
            first = False
            cur = w
        else:
            lines.append((first, w))
            first = False
            cur = ""
    if cur:
        lines.append((first, cur))
    return lines


def image_height(path, width):
    pix = pymupdf.Pixmap(path)
    return width * pix.height / pix.width


def item_height(path, width, caption, head, num):
    h = 15 + 6                                  # header line + gap
    h += image_height(path, width)
    h += 6
    lines = wrap_with_prefix("Screenshot %d. " % num, caption, 8.5, width)
    h += len(lines) * 10.6
    h += 16                                     # gap to the next item
    return h


def main():
    doc = pymupdf.open(SRC)
    assert doc.page_count == 20, doc.page_count

    # assign screenshot numbers in reading order of the finished document
    numbered = []
    n = 0
    for anchor in sorted(PLAN):
        for key, head, caption in PLAN[anchor]:
            n += 1
            numbered.append((anchor, n, key, head, caption))

    # pack the items of one anchor page into as few added pages as possible
    groups = {}
    for anchor, num, key, head, caption in numbered:
        groups.setdefault(anchor, [])
        path = os.path.join(SHOTS, key + ".png")
        item = dict(num=num, key=key, head=head, caption=caption, path=path)
        item["w"] = MAX_W
        item["h"] = item_height(path, MAX_W, caption, head, num)
        gs = groups[anchor]
        if gs and sum(i["h"] for i in gs[-1]) + item["h"] <= PAGE_H - TOP - BOTTOM:
            gs[-1].append(item)
        else:
            gs.append([item])

    # balance the pages: a lone screenshot on the last page looks accidental, so
    # move trailing items from the fuller page down while they still fit
    usable = PAGE_H - TOP - BOTTOM
    for anchor, pages in groups.items():
        for k in range(len(pages) - 1, 0, -1):
            prev, last = pages[k - 1], pages[k]
            while len(prev) > 2 and prev[-1]["h"] + sum(i["h"] for i in last) <= usable:
                last.insert(0, prev.pop())

    # insert from the back so earlier page numbers stay valid
    for anchor in sorted(groups, reverse=True):
        for group in reversed(groups[anchor]):
            page = doc.new_page(pno=anchor, width=PAGE_W, height=PAGE_H)
            page.insert_font(fontname="carlito", fontfile=F_REG)
            page.insert_font(fontname="carlito-bold", fontfile=F_BOLD)
            page.insert_font(fontname="carlito-italic", fontfile=F_ITAL)

            y = TOP
            for item in group:
                # header: step on the left, screenshot number on the right
                page.insert_text((MARGIN_X, y + 9), item["head"], fontname="carlito-bold",
                                 fontsize=10.5, color=NAVY)
                label = "Screenshot %d" % item["num"]
                lw = FONT_ITAL.text_length(label, fontsize=8.5)
                page.insert_text((MARGIN_X + MAX_W - lw, y + 9), label,
                                 fontname="carlito-italic", fontsize=8.5, color=GREY)
                y += 15
                page.draw_line(pymupdf.Point(MARGIN_X, y), pymupdf.Point(MARGIN_X + MAX_W, y),
                               color=RULE, width=0.7)
                y += 7

                pix = pymupdf.Pixmap(item["path"])
                iw = item["w"]
                ih = iw * pix.height / pix.width
                rect = pymupdf.Rect(MARGIN_X, y, MARGIN_X + iw, y + ih)
                page.insert_image(rect, filename=item["path"])
                page.draw_rect(rect, color=RULE, width=0.6)
                y += ih + 7

                num_txt = "Screenshot %d. " % item["num"]
                lines = wrap_with_prefix(num_txt, item["caption"], 8.5, MAX_W)
                for first, line in lines:
                    if first:
                        page.insert_text((MARGIN_X, y + 7), num_txt, fontname="carlito-bold",
                                         fontsize=8.5, color=NAVY)
                        off = FONT_BOLD.text_length(num_txt, fontsize=8.5)
                        page.insert_text((MARGIN_X + off, y + 7), line,
                                         fontname="carlito-italic", fontsize=8.5, color=GREY)
                    else:
                        page.insert_text((MARGIN_X, y + 7), line, fontname="carlito-italic",
                                         fontsize=8.5, color=GREY)
                    y += 10.6
                y += 16

    doc.set_metadata({
        "title": "DEVOPS PROJECT 5: Multi-Cloud Service Mesh Implementation",
        "subject": "Original project brief with implementation screenshots inserted",
        "author": "",
        "creator": "PyMuPDF",
        "producer": "PyMuPDF",
    })
    doc.save(OUT, garbage=3, deflate=True)
    doc.close()

    check = pymupdf.open(OUT)
    print("saved :", OUT)
    print("pages :", check.page_count)
    print("images:", sum(len(p.get_images()) for p in check))
    for i, page in enumerate(check):
        txt = page.get_text().strip().split("\n")[0][:70]
        print(f"  p{i+1:02d}: {txt}")


if __name__ == "__main__":
    main()
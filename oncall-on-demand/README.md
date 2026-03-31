# OnCall On-Demand

A microservices application for managing on-call schedules, tracking primary and secondary shifts, and calculating yearly on-call statistics.

## Architecture

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Frontend   │─────▶│  Calculator  │─────▶│   MongoDB    │
│  (Flask UI)  │      │  (Flask API) │      │  (Database)  │
│  port 5000   │─────▶│  port 5001   │      │  port 27017  │
└──────────────┘      └──────────────┘      └──────────────┘
       │                                           ▲
       └───────────────────────────────────────────┘
```

| Service | Description | Port |
|---------|-------------|------|
| **Frontend** | Flask web app with login, dashboard, and statistics pages | 5000 |
| **Calculator** | REST API that computes yearly on-call shift counts | 5001 |
| **MongoDB** | Stores users and on-call entries | 27017 |

## Technology Stack

This project uses only **standard, well-established libraries and frameworks** — no experimental or proprietary dependencies.

| Layer | Technology | Notes |
|-------|-----------|-------|
| **HTML** | HTML5 | Standard elements only (`form`, `table`, `nav`, `input`, etc.) |
| **CSS** | CSS3 + Bootstrap 5.3 | Standard properties (flexbox, sizing, colors). Bootstrap via CDN |
| **Icons** | Bootstrap Icons 1.11 | Icon font via CDN |
| **Python** | Flask, pymongo, Werkzeug, requests, gunicorn | All pinned to exact versions in `requirements.txt` |
| **Database** | MongoDB 7 | Official `mongo:7` Docker image |
| **Templates** | Jinja2 | Built into Flask — standard Python templating |

No custom web components, no JavaScript frameworks, no compiled CSS preprocessors, no experimental browser APIs.

---

## Project Structure

```
oncall-on-demand/
├── src/
│   ├── frontend/          # Flask web frontend
│   │   ├── app.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── templates/     # Jinja2 HTML templates
│   │   └── static/        # CSS assets
│   ├── calculator/        # Flask calculation API
│   │   ├── app.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── mongodb/           # MongoDB with init script
│       ├── Dockerfile
│       └── init-db.js
├── deploy/
│   └── helm/
│       └── oncall-on-demand/   # Helm chart for Kubernetes (primary deployment)
│           ├── Chart.yaml
│           ├── values.yaml
│           └── templates/
├── docker-compose.yaml    # Backup / local development only
└── README.md
```

## Default Credentials

A default admin user is seeded automatically on first startup:

| Username | Password | Employee ID |
|----------|----------|-------------|
| `admin`  | `admin`  | `ADMIN-001` |

---

## Deployment (Kubernetes via Helm) — Primary

This is the **recommended and primary** deployment method for all environments.

### Prerequisites

- Kubernetes cluster (1.24+)
- Helm 3.x
- Docker (to build images)
- A container registry (Docker Hub, ECR, GCR, Harbor, etc.)

### Step 1 — Build and Push Images

```bash
# Build images
docker build -t <registry>/oncall-frontend:1.0.0   src/frontend/
docker build -t <registry>/oncall-calculator:1.0.0  src/calculator/
docker build -t <registry>/oncall-mongodb:1.0.0     src/mongodb/

# Push to registry
docker push <registry>/oncall-frontend:1.0.0
docker push <registry>/oncall-calculator:1.0.0
docker push <registry>/oncall-mongodb:1.0.0
```

### Step 2 — Deploy with Helm

```bash
helm install oncall deploy/helm/oncall-on-demand/ \
  --namespace oncall \
  --create-namespace \
  --set frontend.image.repository=<registry>/oncall-frontend \
  --set calculator.image.repository=<registry>/oncall-calculator \
  --set mongodb.image.repository=<registry>/oncall-mongodb \
  --set frontend.env.secretKey="your-production-secret"
```

### Step 3 — Verify

```bash
# Check Helm release status
helm status oncall -n oncall

# Check all pods are running
kubectl get pods -n oncall

# View logs
kubectl logs -l app.kubernetes.io/name=frontend  -n oncall -f
kubectl logs -l app.kubernetes.io/name=calculator -n oncall -f
kubectl logs -l app.kubernetes.io/name=mongodb    -n oncall -f
```

### Step 4 — Access the Application

**Option A — Ingress (recommended):**

Requires a one-time NGINX Ingress Controller install (see [Ingress Controller Setup](#ingress-controller-setup) below).
Ingress is **enabled by default** in `values.yaml`.

```bash
# Find the HTTP NodePort assigned by the ingress controller
kubectl get svc -n ingress-nginx ingress-nginx-controller
# Look for 80:<NodePort>/TCP — typically 30080

# Add DNS entry pointing to your node
echo '<node-ip> oncall-on-demand.com' | sudo tee -a /etc/hosts

# Access the application
curl http://oncall-on-demand.com:30080/health
# Or open http://oncall-on-demand.com:30080 in a browser
```

**Option B — Port-forward (quick test, no ingress needed):**

```bash
kubectl port-forward svc/frontend 8080:80 -n oncall
# Open http://localhost:8080
```

> **Note:** Port 5000 is typically used by the local Docker registry. Use port 8080
> (or any free port) for the frontend port-forward to avoid conflicts.

### Upgrade and Rollback

```bash
# Upgrade to a new version
helm upgrade oncall deploy/helm/oncall-on-demand/ \
  --namespace oncall \
  --set frontend.image.tag=1.1.0 \
  --set calculator.image.tag=1.1.0 \
  --set mongodb.image.tag=1.1.0

# Rollback if something goes wrong
helm rollback oncall -n oncall

# Uninstall
helm uninstall oncall -n oncall
```

### Helm Chart Resources

The chart deploys the following 13 Kubernetes resources into the `oncall` namespace:

| Resource | Name | Details |
|----------|------|---------|
| ServiceAccount | oncall-on-demand | Shared by all pods |
| Secret | oncall-secrets | Flask session secret key |
| PersistentVolumeClaim | mongodb-data | 5Gi storage for MongoDB |
| Service | `mongodb` | ClusterIP, port 27017 |
| Service | `calculator` | ClusterIP, port 80 → 5001 |
| Service | `frontend` | ClusterIP, port 80 → 5000 |
| Deployment | mongodb | 1 replica, Recreate strategy |
| Deployment | calculator | 2 replicas, init container waits for MongoDB |
| Deployment | frontend | 2 replicas, init container waits for MongoDB |
| NetworkPolicy | frontend | Allows ingress; egress to calculator + MongoDB + DNS |
| NetworkPolicy | calculator | Ingress from frontend only; egress to MongoDB + DNS |
| NetworkPolicy | mongodb | Ingress from frontend + calculator only |
| Ingress | oncall-ingress | Enabled by default; routes `oncall-on-demand.com` → frontend |

### Ingress Controller Setup

The Helm chart creates an **Ingress resource**, but you also need an **Ingress Controller** running in the cluster to act on it. The controller is a pod running a reverse proxy (NGINX) that reads Ingress resources and configures routing automatically.

```
Browser → http://oncall-on-demand.com:30080
                │
                ▼
        Node (port 30080 via NodePort)
                │
                ▼
    ┌───────────────────────────┐
    │ NGINX Ingress Controller  │  Reads Ingress resources,
    │ (pod in ingress-nginx ns) │  routes by hostname/path
    └──────────┬────────────────┘
               │ host: oncall-on-demand.com, path: /
               ▼
    ┌──────────────────────┐
    │ frontend Service (:80)│ → frontend pods (:5000)
    └──────────────────────┘
```

**Install (one-time, bare-metal/kubeadm):**

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/baremetal/deploy.yaml

# Wait for the controller pod to be ready
kubectl get pods -n ingress-nginx -w
# NAME                                        READY   STATUS    AGE
# ingress-nginx-controller-xxxxxxxxxx-xxxxx   1/1     Running   ...
```

**Find the assigned NodePort:**

```bash
kubectl get svc -n ingress-nginx ingress-nginx-controller
# NAME                       TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)                      AGE
# ingress-nginx-controller   NodePort   10.x.x.x       <none>        80:30080/TCP,443:30443/TCP   ...
```

The HTTP port (80) is mapped to NodePort **30080** on your node. HTTPS (443) maps to **30443**.

**Add DNS and test:**

```bash
echo '<node-ip> oncall-on-demand.com' | sudo tee -a /etc/hosts

# Test — should return the frontend health JSON
curl -s http://oncall-on-demand.com:30080/health | python3 -m json.tool
```

**Key concepts:**

| Concept | What it does |
|---------|-------------|
| **Ingress Resource** | A Kubernetes object (your `ingress.yaml`) declaring routing rules: "send traffic for host X to service Y" |
| **Ingress Controller** | A pod (NGINX) that watches Ingress resources and applies the routing rules |
| **IngressClass** | Links an Ingress to a specific controller (`className: nginx` in `values.yaml`) |
| **NodePort** | How the controller is exposed on bare-metal — maps node port 30080 to controller port 80 |

> **Note:** On cloud providers (AWS/GCP/Azure), the ingress controller uses a `LoadBalancer`
> service instead of `NodePort`, and you get an external IP or DNS name automatically.

### Customizing values.yaml

Key values you may want to override:

```yaml
# Scale replicas
frontend.replicaCount: 3
calculator.replicaCount: 3

# Use a private registry
global.imagePullSecrets:
  - name: my-registry-secret

# Increase MongoDB storage
mongodb.storage.size: 20Gi
mongodb.storage.storageClassName: gp3

# Set production secret
frontend.env.secretKey: "a-long-random-production-secret"

# Enable ingress with TLS
ingress.enabled: true
ingress.host: oncall-on-demand.com
ingress.className: nginx
ingress.tls:
  - secretName: oncall-tls
    hosts:
      - oncall-on-demand.com
```

---

## Deployment on Ubuntu (Kubernetes)

Full instructions for deploying on a fresh Ubuntu system with Kubernetes.

> **Using a single-node kubeadm cluster for learning?** See the dedicated
> [Single-Node kubeadm Deployment](#single-node-kubeadm-deployment-learning) section below
> for a complete step-by-step walkthrough including taint removal, CNI, storage, and ingress setup.

### Prerequisites

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install -y docker.io
sudo usermod -aG docker $USER
newgrp docker

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
docker --version
kubectl version --client
helm version --short
```

> If you don't have a full Kubernetes cluster, you can use **kubeadm**, **minikube**, or **k3s**:
>
> ```bash
> # Option A: kubeadm (recommended for learning real Kubernetes)
> # See "Single-Node kubeadm Deployment" section below
>
> # Option B: minikube
> curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
> sudo install minikube-linux-amd64 /usr/local/bin/minikube
> minikube start
>
> # Option C: k3s (lightweight, includes Traefik ingress + local-path storage)
> curl -sfL https://get.k3s.io | sh -
> export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
> ```

### Build, Push, and Deploy

```bash
# Clone the project
git clone <your-repo-url> oncall-on-demand
cd oncall-on-demand

# Build images
docker build -t <registry>/oncall-frontend:1.0.0   src/frontend/
docker build -t <registry>/oncall-calculator:1.0.0  src/calculator/
docker build -t <registry>/oncall-mongodb:1.0.0     src/mongodb/

# Push to registry
docker push <registry>/oncall-frontend:1.0.0
docker push <registry>/oncall-calculator:1.0.0
docker push <registry>/oncall-mongodb:1.0.0

# Deploy with Helm
helm install oncall deploy/helm/oncall-on-demand/ \
  --namespace oncall \
  --create-namespace \
  --set frontend.image.repository=<registry>/oncall-frontend \
  --set calculator.image.repository=<registry>/oncall-calculator \
  --set mongodb.image.repository=<registry>/oncall-mongodb \
  --set frontend.env.secretKey="your-production-secret"

# Verify pods
kubectl get pods -n oncall -w
```

### Access via Ingress (recommended)

```bash
# Install the NGINX Ingress Controller (one-time, see Ingress Controller Setup section)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/baremetal/deploy.yaml

# Wait for it to be ready
kubectl get pods -n ingress-nginx -w

# Find the HTTP NodePort (look for 80:<port>/TCP, e.g. 80:30080/TCP)
kubectl get svc -n ingress-nginx ingress-nginx-controller

# Add local DNS entry
echo '127.0.0.1 oncall-on-demand.com' | sudo tee -a /etc/hosts

# Access the application via Ingress on port 30080
curl http://oncall-on-demand.com:30080/health
# Or open http://oncall-on-demand.com:30080 in a browser
```

### Access via Port-Forward (alternative)

```bash
# Use 8080 since 5000 is occupied by Docker registry
kubectl port-forward svc/frontend 8080:80 -n oncall
# Open http://localhost:8080
```

### Portability Notes

| Item | Detail |
|------|--------|
| **Architecture** | All base images (`python:3.12-slim`, `mongo:7`) are multi-arch — works on both amd64 and arm64 Ubuntu |
| **Dependencies** | All Python packages are pinned to exact versions in `requirements.txt` for reproducible builds |
| **No host dependencies** | Everything runs inside containers — no Python, MongoDB, or other tooling needed on the host |
| **Data persistence** | MongoDB uses a PersistentVolumeClaim (5Gi) that survives pod restarts |
| **Standard stack** | HTML5, CSS3, Python/Flask — no non-standard or experimental libraries (see [Technology Stack](#technology-stack)) |

---

## Single-Node kubeadm Deployment (Learning)

A complete walkthrough for deploying on a **single-node kubeadm cluster** — the most common learning setup on a Linux VM or bare-metal machine.

### Prerequisites

| Tool | Purpose |
|------|---------|
| Ubuntu 22.04+ (or similar) | Host OS |
| kubeadm, kubelet, kubectl | Kubernetes cluster bootstrap |
| Docker CE | Build container images |
| Helm 3.x | Deploy the Helm chart |

### Step 1 — Remove the control-plane taint

By default, kubeadm taints the control-plane node with `NoSchedule`, which **prevents all workload pods from being scheduled** on a single-node cluster. This is the most common reason pods stay in `Pending` forever.

```bash
# Remove the taint so pods can run on the control-plane node
kubectl taint nodes --all node-role.kubernetes.io/control-plane-

# Verify — the TAINTS column should show <none>
kubectl get nodes -o wide
```

> **Why this is needed:** In multi-node clusters, the taint keeps the control-plane dedicated to
> system components. On a single-node learning cluster, it must be removed or nothing will schedule.

### Step 2 — Install a CNI plugin

kubeadm requires a CNI (Container Network Interface) plugin for pod networking. **Calico** is recommended because it also enforces the NetworkPolicy resources in this Helm chart.

```bash
# Install Calico (supports NetworkPolicy enforcement)
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/calico.yaml

# Wait for Calico pods to be ready
kubectl get pods -n kube-system -l k8s-app=calico-node -w
```

> **Note on flannel:** If you use flannel instead, the cluster will work, but the
> NetworkPolicy resources will be created and silently ignored — traffic between pods
> will not be restricted. For learning purposes this is acceptable.

### Step 3 — Install a storage provisioner

kubeadm does not include a default StorageClass. Without one, the MongoDB PersistentVolumeClaim will stay `Pending`.

```bash
# Install local-path-provisioner (creates PVs on local disk)
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml

# Make it the default StorageClass
kubectl patch storageclass local-path -p \
  '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Verify
kubectl get storageclass
# NAME                   PROVISIONER             AGE
# local-path (default)   rancher.io/local-path   ...
```

### Step 4 — Install NGINX Ingress Controller

```bash
# Install the bare-metal manifest (creates a NodePort service)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/baremetal/deploy.yaml

# Wait for the controller pod
kubectl get pods -n ingress-nginx -w

# Find the HTTP NodePort (look for 80:<port>/TCP, typically 30080)
kubectl get svc -n ingress-nginx ingress-nginx-controller
```

### Step 5 — Set up a local Docker registry

Images built with Docker are not visible to containerd (which Kubernetes uses). You need a registry as a bridge.

```bash
# Start a local registry on port 5000
docker run -d -p 5000:5000 --restart=always --name registry registry:2

# Configure containerd to pull from it (insecure/HTTP)
sudo tee -a /etc/containerd/config.toml <<'EOF'

[plugins."io.containerd.grpc.v1.cri".registry.configs."localhost:5000".tls]
  insecure_skip_verify = true
[plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]
  endpoint = ["http://localhost:5000"]
EOF

sudo systemctl restart containerd
```

### Step 6 — Build, push, and deploy

```bash
# Clone the project
git clone <your-repo-url> oncall-on-demand
cd oncall-on-demand

# Build and push images to the local registry
docker build -t localhost:5000/oncall-frontend:1.0.0   src/frontend/
docker build -t localhost:5000/oncall-calculator:1.0.0  src/calculator/
docker build -t localhost:5000/oncall-mongodb:1.0.0     src/mongodb/

docker push localhost:5000/oncall-frontend:1.0.0
docker push localhost:5000/oncall-calculator:1.0.0
docker push localhost:5000/oncall-mongodb:1.0.0

# Deploy with Helm
helm install oncall deploy/helm/oncall-on-demand/ \
  --namespace oncall \
  --create-namespace \
  --set frontend.image.repository=localhost:5000/oncall-frontend \
  --set calculator.image.repository=localhost:5000/oncall-calculator \
  --set mongodb.image.repository=localhost:5000/oncall-mongodb \
  --set mongodb.storage.storageClassName=local-path \
  --set frontend.env.secretKey="your-secret-key"

# Wait for all pods to be Running
kubectl get pods -n oncall -w
```

### Step 7 — Access the application

```bash
# Add DNS entry (use the node's IP or 127.0.0.1 if accessing locally)
echo '127.0.0.1 oncall-on-demand.com' | sudo tee -a /etc/hosts

# Access via Ingress (NodePort 30080)
curl http://oncall-on-demand.com:30080/health
# Or open http://oncall-on-demand.com:30080 in a browser
```

### Single-node checklist

Use this checklist to diagnose issues on a single-node kubeadm cluster:

| Check | Command | Expected |
|-------|---------|----------|
| Taint removed | `kubectl describe node \| grep Taints` | `<none>` |
| CNI running | `kubectl get pods -n kube-system -l k8s-app=calico-node` | `Running` |
| StorageClass exists | `kubectl get storageclass` | `local-path (default)` |
| Ingress controller running | `kubectl get pods -n ingress-nginx` | `Running` |
| Registry accessible | `curl -s http://localhost:5000/v2/_catalog` | `{"repositories":[...]}` |
| All app pods running | `kubectl get pods -n oncall` | All `Running` |
| PVC bound | `kubectl get pvc -n oncall` | `Bound` |
| Ingress has address | `kubectl get ingress -n oncall` | Shows `ADDRESS` |

### Reducing resource usage (optional)

For resource-constrained VMs (2 CPU / 4 GB RAM), reduce replica counts:

```bash
helm install oncall deploy/helm/oncall-on-demand/ \
  --namespace oncall \
  --create-namespace \
  --set frontend.replicaCount=1 \
  --set calculator.replicaCount=1 \
  --set frontend.image.repository=localhost:5000/oncall-frontend \
  --set calculator.image.repository=localhost:5000/oncall-calculator \
  --set mongodb.image.repository=localhost:5000/oncall-mongodb \
  --set mongodb.storage.storageClassName=local-path
```

---

## Backup Deployment (Docker Compose) — Local Dev Only

> **This is a backup deployment method** for local development and testing when a
> Kubernetes cluster is not available. For production, use the Helm chart above.

### Prerequisites

- Docker and Docker Compose V2

```bash
# Ubuntu
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER && newgrp docker

# macOS — Docker Desktop includes Compose V2
```

### Run

```bash
cd oncall-on-demand

# Build and start all services
docker compose up --build -d

# Verify
docker compose ps

# Access the application
# http://localhost:5000
# http://oncall-on-demand.com (if /etc/hosts entry added)
```

### Custom Domain (optional)

```bash
echo '127.0.0.1 oncall-on-demand.com' | sudo tee -a /etc/hosts
# Then open http://oncall-on-demand.com
```

> **Note:** Port 80 binding on Linux requires elevated privileges. Remove the
> `"80:5000"` line from `docker-compose.yaml` if you prefer to use `localhost:5000` only.

### Logs and Troubleshooting

```bash
docker compose logs -f              # All services
docker compose logs -f frontend     # Frontend only
curl http://localhost:5000/health   # Frontend health
curl http://localhost:5001/api/health  # Calculator health
```

### Teardown

```bash
docker compose down        # Stop and remove containers
docker compose down -v     # Also delete MongoDB data volume
```

---

## API Endpoints

> **Kubernetes (Ingress):** Use `oncall-on-demand.com:30080` for the frontend via Ingress (recommended).
>
> **Kubernetes (port-forward):** Use `localhost:8080` (frontend) and `localhost:8081` (calculator)
> as a fallback, since port 5000 is reserved for the local Docker registry.
>
> **Docker Compose:** Uses `localhost:5000` (frontend) and `localhost:5001` (calculator) directly.

### Frontend

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/login` | User authentication |
| GET/POST | `/register` | New user registration |
| GET/POST | `/dashboard` | On-call entry management |
| GET | `/stats?year=2026` | Yearly statistics |
| GET | `/health` | Health check |

#### curl Examples — Frontend (Kubernetes via Ingress — recommended)

```bash
# Health check (Ingress routes oncall-on-demand.com → frontend service)
curl -s http://oncall-on-demand.com:30080/health | python3 -m json.tool

# Login
curl -X POST http://oncall-on-demand.com:30080/login \
  -d "username=admin&password=admin" \
  -c cookies.txt -L

# Add an on-call entry
curl -X POST http://oncall-on-demand.com:30080/dashboard \
  -b cookies.txt \
  -d "username=admin&employee_id=ADMIN-001&oncall_primary_date=2026-04-07&oncall_secondary_date=2026-04-14" \
  -L

# View statistics
curl -s http://oncall-on-demand.com:30080/stats?year=2026 -b cookies.txt

# Clean up
rm -f cookies.txt
```

#### curl Examples — Frontend (Kubernetes via port-forward — fallback)

```bash
# Start port-forward first (port 5000 is used by Docker registry, so use 8080)
kubectl port-forward svc/frontend 8080:80 -n oncall &

# Health check
curl -s http://localhost:8080/health | python3 -m json.tool

# Register a new user
curl -X POST http://localhost:8080/register \
  -d "username=jdoe&password=secret123&employee_id=EMP-042" \
  -L

# Login (stores session cookie in cookie jar for subsequent requests)
curl -X POST http://localhost:8080/login \
  -d "username=admin&password=admin" \
  -c cookies.txt \
  -L

# Add an on-call entry (requires login cookie)
curl -X POST http://localhost:8080/dashboard \
  -b cookies.txt \
  -d "username=admin&employee_id=ADMIN-001&oncall_primary_date=2026-04-07&oncall_secondary_date=2026-04-14" \
  -L

# Add another on-call entry
curl -X POST http://localhost:8080/dashboard \
  -b cookies.txt \
  -d "username=admin&employee_id=ADMIN-001&oncall_primary_date=2026-06-15&oncall_secondary_date=2026-06-22" \
  -L

# View statistics page (HTML response)
curl -s http://localhost:8080/stats?year=2026 \
  -b cookies.txt

# Logout
curl -s http://localhost:8080/logout \
  -b cookies.txt \
  -L

# Clean up cookie jar
rm -f cookies.txt
```

#### curl Examples — Frontend (Docker Compose)

```bash
# Docker Compose exposes frontend directly on port 5000
curl -s http://localhost:5000/health | python3 -m json.tool

curl -X POST http://localhost:5000/login \
  -d "username=admin&password=admin" \
  -c cookies.txt -L
```

### Calculator

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/calculate/<username>?year=2026` | Get shift counts |
| GET | `/api/health` | Health check |

#### curl Examples — Calculator (Kubernetes via port-forward)

```bash
# Start port-forward first
kubectl port-forward svc/calculator 8081:80 -n oncall &

# Health check (returns JSON)
curl -s http://localhost:8081/api/health | python3 -m json.tool
# {
#     "mongodb": "connected",
#     "service": "calculator",
#     "status": "healthy"
# }

# Calculate on-call shifts for a user in a given year
curl -s "http://localhost:8081/api/calculate/admin?year=2026" | python3 -m json.tool
# {
#     "primary_count": 2,
#     "secondary_count": 2,
#     "total_shifts": 4,
#     "username": "admin",
#     "year": 2026
# }

# Calculate for a different year
curl -s "http://localhost:8081/api/calculate/admin?year=2025" | python3 -m json.tool
# {
#     "primary_count": 0,
#     "secondary_count": 0,
#     "total_shifts": 0,
#     "username": "admin",
#     "year": 2025
# }

# Calculate for a different user
curl -s "http://localhost:8081/api/calculate/jdoe?year=2026" | python3 -m json.tool
```

#### curl Examples — Calculator (Docker Compose)

```bash
# Docker Compose exposes calculator directly on port 5001
curl -s http://localhost:5001/api/health | python3 -m json.tool
curl -s "http://localhost:5001/api/calculate/admin?year=2026" | python3 -m json.tool
```

### Accessing via Kubernetes

**Via Ingress (recommended — no manual port-forward needed):**

Requires the NGINX Ingress Controller and `/etc/hosts` entry (see [Ingress Controller Setup](#ingress-controller-setup)).

```bash
# Frontend — routed through Ingress on port 30080
curl -s http://oncall-on-demand.com:30080/health | python3 -m json.tool

# Calculator — not exposed via Ingress; use port-forward if needed
kubectl port-forward svc/calculator 8081:80 -n oncall &
curl -s http://localhost:8081/api/health | python3 -m json.tool
curl -s "http://localhost:8081/api/calculate/admin?year=2026" | python3 -m json.tool
kill %1
```

**Via port-forward (fallback — no ingress required):**

```bash
# Forward frontend (K8s service port 80 -> localhost:8080)
kubectl port-forward svc/frontend 8080:80 -n oncall &

# Forward calculator (K8s service port 80 -> localhost:8081)
kubectl port-forward svc/calculator 8081:80 -n oncall &

# Now use the curl commands against localhost:8080 and localhost:8081
curl -s http://localhost:8080/health | python3 -m json.tool
curl -s http://localhost:8081/api/health | python3 -m json.tool
curl -s "http://localhost:8081/api/calculate/admin?year=2026" | python3 -m json.tool

# Stop port-forwards when done
kill %1 %2
```

### Port allocation summary

| Port | Used by | Context |
|------|---------|---------|
| `5000` | Docker registry | Local container image registry |
| `30080` | NGINX Ingress Controller (HTTP) | Ingress routes to frontend via hostname (`oncall-on-demand.com:30080`) |
| `30443` | NGINX Ingress Controller (HTTPS) | TLS ingress (when TLS is configured) |
| `8080` | Frontend (via port-forward) | Fallback: `kubectl port-forward svc/frontend 8080:80` |
| `8081` | Calculator (via port-forward) | Fallback: `kubectl port-forward svc/calculator 8081:80` |
| `27017` | MongoDB | Internal to cluster (not exposed externally) |

---

## Troubleshooting and Operations Guide

A complete guide covering all known issues, their causes, and fixes — compiled from real deployment experience.

### 1. Frontend crashes with `DuplicateKeyError` on startup

**Symptom:**
```
pymongo.errors.DuplicateKeyError: E11000 duplicate key error collection:
oncall_db.users index: username_1 dup key: { username: "admin" }
Worker failed to boot.
```

**Cause:** Gunicorn starts multiple workers in parallel. Both workers try to seed the default admin user simultaneously — one succeeds, the other hits the unique index constraint and crashes.

**Fix:** Already fixed in the codebase. The `seed_default_admin()` function uses `update_one` with `upsert=True` and catches `DuplicateKeyError`. If you see this error, make sure you're running the latest version of `src/frontend/app.py`.

---

### 2. MongoDB pod stuck in `Pending` — unbound PersistentVolumeClaim

**Symptom:**
```
0/1 nodes are available: pod has unbound immediate PersistentVolumeClaims.
preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
```

**Cause:** Your Kubernetes cluster has no StorageClass or dynamic volume provisioner. Common on bare-metal / kubeadm single-node setups.

**Diagnose:**
```bash
kubectl get storageclass
# If output says "No resources found" — that's the problem

kubectl get pvc -n oncall
# PVC will show status: Pending
```

**Fix — Install local-path-provisioner (recommended for learning/dev):**
```bash
# Install the provisioner
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml

# Make it the default StorageClass
kubectl patch storageclass local-path -p \
  '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Delete the stuck PVC so it gets recreated
kubectl delete pvc oncall-oncall-on-demand-mongodb-data -n oncall

# Upgrade the Helm release to use it
helm upgrade oncall deploy/helm/oncall-on-demand/ \
  --namespace oncall \
  --set mongodb.storage.storageClassName=local-path \
  --reuse-values

# Verify PVC is now Bound
kubectl get pvc -n oncall
```

**What is local-path-provisioner?** It's a lightweight storage provisioner by Rancher that creates PersistentVolumes using directories on the node's local disk (`/opt/local-path-provisioner/`). It watches for PVC requests, creates a directory, and binds the PV. Not for production (no replication, no multi-node support), but ideal for single-node learning clusters.

**Alternative — Create a manual PersistentVolume:**
```bash
sudo mkdir -p /data/oncall-mongodb

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
  name: oncall-mongodb-pv
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteOnce
  hostPath:
    path: /data/oncall-mongodb
  claimRef:
    namespace: oncall
    name: oncall-oncall-on-demand-mongodb-data
EOF
```

---

### 3. Docker push fails with `EOF` error to local registry

**Symptom:**
```
failed to do request: Head "https://localhost:5050/v2/oncall-frontend/blobs/sha256:...": EOF
```

**Cause:** The local registry container serves plain HTTP, but Docker's client defaults to HTTPS for non-standard ports. The TLS handshake fails and the connection drops.

**Fix — Option A: Tell Docker to allow insecure registry:**
```bash
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "insecure-registries": ["localhost:5050"]
}
EOF

sudo systemctl restart docker
```

**Fix — Option B: Use port 5000 (recommended — Docker has a built-in HTTP exception for `localhost:5000`):**
```bash
# Stop old registry if running on a different port
docker stop registry && docker rm registry

# Start registry on port 5000
docker run -d -p 5000:5000 --restart=always --name registry registry:2

# Tag and push (no daemon.json change needed for localhost:5000)
docker build -t localhost:5000/oncall-frontend:1.0.0   src/frontend/
docker push localhost:5000/oncall-frontend:1.0.0
```

> **Important:** Since the Docker registry occupies port 5000, use ports 8080/8081
> for `kubectl port-forward` to the frontend and calculator services respectively.
> See [Port allocation summary](#port-allocation-summary) above.

**Also configure containerd** (so Kubernetes can pull from the same local registry):
```bash
sudo tee -a /etc/containerd/config.toml <<'EOF'

[plugins."io.containerd.grpc.v1.cri".registry.configs."localhost:5000".tls]
  insecure_skip_verify = true
[plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]
  endpoint = ["http://localhost:5000"]
EOF

sudo systemctl restart containerd
kubectl get nodes  # Verify still Ready
```

---

### 4. Installing Docker CE on a system already running containerd (for Kubernetes)

**Situation:** Kubernetes uses containerd as its runtime. You want Docker CE for building images.

**Key facts:**
- Docker CE and containerd coexist safely — they use separate sockets and image stores
- `docker-ce` has a hard dependency on the `containerd.io` package
- `containerd.io` (from Docker's repo) is a 1:1 replacement for `containerd` (from Ubuntu's repo)
- Installing it will remove the `containerd` Ubuntu package and install `containerd.io` — **this is safe**

| Component | Socket | Image store | Purpose |
|-----------|--------|-------------|---------|
| Docker | `/var/run/docker.sock` | `/var/lib/docker/` | Build and push images |
| containerd | `/run/containerd/containerd.sock` | `/var/lib/containerd/` | Kubernetes pod runtime |

**Install procedure:**
```bash
# Remove Ubuntu's docker.io if present (avoid conflicts)
sudo apt remove -y docker.io docker-compose 2>/dev/null

# Install Docker CE official packages
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

**CRITICAL — When asked about `/etc/containerd/config.toml`:**
```
Configuration file '/etc/containerd/config.toml'
 ==> Modified since installation.
 ==> Package distributor has shipped an updated version.
   What would you like to do about it?
    Y or I  : install the package maintainer's version
    N or O  : keep your currently-installed version
```

**Choose `N`** — keep your existing version. Your current `config.toml` has Kubernetes-specific settings (CRI plugin, cgroup driver, sandbox image). Overwriting it will break Kubernetes.

If you accidentally chose `Y`, restore the backup:
```bash
sudo cp /etc/containerd/config.toml.dpkg-old /etc/containerd/config.toml
sudo systemctl restart containerd
```

**Verify after installation:**
```bash
docker --version               # Docker CE working
docker compose version         # Compose V2 plugin
sudo systemctl status containerd  # containerd still running
kubectl get nodes              # Kubernetes still Ready
kubectl get pods -A            # All pods healthy
```

---

### 5. Port conflicts and binding issues

**Symptom A:** `kubectl port-forward` fails with "port already bound".

**Cause:** The local Docker registry is already running on port 5000. You cannot forward to a port that is in use.

**Fix:** Use port 8080 for frontend and 8081 for calculator:
```bash
kubectl port-forward svc/frontend 8080:80 -n oncall
kubectl port-forward svc/calculator 8081:80 -n oncall
```

**Symptom B:** `docker compose up` fails to bind port 80, or Kubernetes `port-forward` to port 80 requires sudo.

**Cause:** Linux requires root privileges for ports below 1024.

**Fix options:**
```bash
# Option A: Use sudo
sudo docker compose up --build -d

# Option B: Use port 5000 only (remove port 80 mapping from docker-compose.yaml)
# Change:  "80:5000" → remove this line, keep "5000:5000"

# Option C: Allow non-root binding (system-wide)
sudo sysctl net.ipv4.ip_unprivileged_port_start=80
```

---

### 6. Images built with Docker not visible to Kubernetes/containerd

**Symptom:** Pods fail with `ErrImagePull` or `ImagePullBackOff` even though you just built the image.

**Cause:** Docker and containerd have separate image stores. An image in Docker's store is invisible to containerd.

**Fix — Images must go through a registry:**

| Method | Command | Best for |
|--------|---------|----------|
| **Remote registry** | `docker push <registry>/image:tag` | Production, CI/CD |
| **Local registry** | `docker push localhost:5000/image:tag` | Dev, air-gapped (registry on port 5000) |
| **Direct import** | `docker save img \| sudo ctr -n k8s.io images import -` | Quick one-off testing |

---

### 7. `nerdctl` as an alternative to Docker (containerd-only systems)

If you don't want to install Docker at all, use `nerdctl` — a Docker-compatible CLI for containerd:

```bash
# Install nerdctl full bundle (includes BuildKit)
curl -LO https://github.com/containerd/nerdctl/releases/latest/download/nerdctl-full-2.0.3-linux-amd64.tar.gz
sudo tar -xzf nerdctl-full-2.0.3-linux-amd64.tar.gz -C /usr/local

# Use it exactly like Docker
nerdctl build -t localhost:5000/oncall-frontend:1.0.0 src/frontend/
nerdctl push localhost:5000/oncall-frontend:1.0.0
nerdctl compose up --build -d
```

| Docker command | nerdctl equivalent |
|---|---|
| `docker build` | `nerdctl build` |
| `docker push` | `nerdctl push` |
| `docker compose up` | `nerdctl compose up` |
| `docker ps` | `nerdctl ps` |

---

### 8. Checking MongoDB data manually

**Via Docker Compose:**
```bash
docker exec -it oncall-on-demand-mongodb-1 mongosh oncall_db

# Inside mongosh:
db.users.find().pretty()
db.oncall_entries.find().pretty()
db.oncall_entries.countDocuments({ username: "admin" })
show collections
exit
```

**Via Kubernetes:**
```bash
# Get the MongoDB pod name
kubectl get pods -n oncall -l app.kubernetes.io/name=mongodb

# Exec into it
kubectl exec -it <mongodb-pod-name> -n oncall -- mongosh oncall_db

# Same mongosh commands as above
```

**One-liner without entering the shell:**
```bash
# Docker Compose
docker exec oncall-on-demand-mongodb-1 mongosh oncall_db --eval "db.users.find().toArray()"

# Kubernetes
kubectl exec <mongodb-pod-name> -n oncall -- mongosh oncall_db --eval "db.users.find().toArray()"
```

---

### 9. Complete teardown

**Kubernetes:**
```bash
# Uninstall the Helm release
helm uninstall oncall -n oncall

# Delete the namespace (removes all resources including PVCs)
kubectl delete namespace oncall

# Remove local-path-provisioner if no longer needed
kubectl delete -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml
```

**Docker Compose:**
```bash
docker compose down -v   # Stop containers + delete volumes
```

**Cleanup host:**
```bash
# Remove /etc/hosts entry
sudo sed -i '/oncall-on-demand\.com/d' /etc/hosts

# Remove local registry (if used)
docker stop registry && docker rm registry

# Remove built images
docker rmi $(docker images "*/oncall-*" -q) 2>/dev/null
docker rmi $(docker images "oncall-on-demand-*" -q) 2>/dev/null
```

---

### Quick diagnostic commands

```bash
# ── Kubernetes ──
kubectl get pods -n oncall                          # Pod status
kubectl get pvc -n oncall                           # Storage status
kubectl get svc -n oncall                           # Service endpoints
kubectl describe pod <pod-name> -n oncall           # Detailed pod info
kubectl logs <pod-name> -n oncall                   # Pod logs
kubectl logs <pod-name> -n oncall -c wait-for-mongodb  # Init container logs
helm status oncall -n oncall                        # Helm release status
helm history oncall -n oncall                       # Release history

# ── Docker Compose ──
docker compose ps                                   # Container status
docker compose logs -f <service>                    # Service logs
docker compose top                                  # Running processes

# ── Health checks (Kubernetes — via Ingress on port 30080) ──
curl -s http://oncall-on-demand.com:30080/health | python3 -m json.tool

# ── Health checks (Kubernetes — via port-forward fallback) ──
curl -s http://localhost:8080/health | python3 -m json.tool
curl -s http://localhost:8081/api/health | python3 -m json.tool

# ── Health checks (Docker Compose) ──
curl -s http://localhost:5000/health | python3 -m json.tool
curl -s http://localhost:5001/api/health | python3 -m json.tool
```

---

## Environment Variables

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `MONGO_URI` | frontend, calculator | `mongodb://mongodb:27017` | MongoDB connection string |
| `DB_NAME` | frontend, calculator | `oncall_db` | Database name |
| `CALCULATOR_URL` | frontend | `http://calculator:5001` | Calculator service URL |
| `SECRET_KEY` | frontend | `dev-secret-key` | Flask session secret |
| `FLASK_DEBUG` | frontend, calculator | `false` | Enable debug mode |

---

## Kubernetes and Helm Concepts Reference

A complete reference for every Kubernetes and Helm concept used in this project, with explanations and examples drawn directly from this application.

---

### Pod

The smallest deployable unit in Kubernetes. A Pod wraps one or more containers that share networking and storage. In this project, each component (frontend, calculator, MongoDB) runs as a Pod.

```yaml
# You don't create Pods directly — Deployments manage them.
# But a Pod spec looks like this inside a Deployment:
spec:
  containers:
    - name: frontend
      image: localhost:5000/oncall-frontend:1.0.0
      ports:
        - containerPort: 5000
```

```bash
# List all pods in the oncall namespace
kubectl get pods -n oncall

# View details of a specific pod
kubectl describe pod <pod-name> -n oncall

# View logs from a pod
kubectl logs <pod-name> -n oncall

# Execute a command inside a running pod
kubectl exec -it <pod-name> -n oncall -- /bin/sh
```

---

### Deployment

A Deployment manages a set of identical Pods (replicas), handles rolling updates, and restarts failed Pods automatically. It is the most common way to run stateless applications.

**How this project uses it:** Three Deployments — `frontend` (2 replicas), `calculator` (2 replicas), `mongodb` (1 replica, Recreate strategy).

```yaml
# From deploy/helm/oncall-on-demand/templates/frontend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oncall-frontend
  namespace: oncall
spec:
  replicas: 2                    # Run 2 identical pods
  selector:
    matchLabels:                 # Deployment manages pods with these labels
      app.kubernetes.io/name: frontend
  template:                      # Pod template — what each replica looks like
    metadata:
      labels:
        app.kubernetes.io/name: frontend
    spec:
      containers:
        - name: frontend
          image: localhost:5000/oncall-frontend:1.0.0
          ports:
            - containerPort: 5000
```

**Key fields explained:**

| Field | Purpose |
|-------|---------|
| `replicas` | Number of identical Pods to run |
| `selector.matchLabels` | How the Deployment finds its Pods |
| `template` | Blueprint for creating new Pods |
| `strategy.type` | `RollingUpdate` (default, zero-downtime) or `Recreate` (stop all, then start — used for MongoDB) |

```bash
# List deployments
kubectl get deployments -n oncall

# Scale a deployment
kubectl scale deployment oncall-frontend --replicas=3 -n oncall

# View rollout status
kubectl rollout status deployment oncall-frontend -n oncall

# Rollback to previous version
kubectl rollout undo deployment oncall-frontend -n oncall

# View rollout history
kubectl rollout history deployment oncall-frontend -n oncall
```

---

### ReplicaSet

A ReplicaSet ensures a specified number of Pod replicas are running at all times. You almost never create ReplicaSets directly — Deployments create and manage them for you.

```bash
# View ReplicaSets (notice each Deployment has one)
kubectl get replicasets -n oncall

# Example output:
# NAME                          DESIRED   CURRENT   READY   AGE
# oncall-frontend-7b9f4c8d6f    2         2         2       5m
# oncall-calculator-5c8d9e7f3a  2         2         2       5m
# oncall-mongodb-4a6b8c2d1e     1         1         1       5m
```

During a rolling update, the Deployment creates a **new** ReplicaSet (with the updated image) and scales it up while scaling down the **old** ReplicaSet.

---

### Service

A Service provides a stable network endpoint (DNS name + IP) for a set of Pods. Pods come and go, but the Service name stays the same. Other Pods use the Service name to communicate.

**How this project uses it:** Three Services — `frontend`, `calculator`, `mongodb`. The frontend talks to `http://calculator:80` and `mongodb:27017` using Service DNS names.

```yaml
# From deploy/helm/oncall-on-demand/templates/frontend-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend              # Other pods reach this as "frontend" or "frontend.oncall.svc.cluster.local"
  namespace: oncall
spec:
  type: ClusterIP              # Only accessible inside the cluster
  ports:
    - port: 80                 # The port other services connect to
      targetPort: 5000         # The port the container listens on
      protocol: TCP
  selector:                    # Routes traffic to pods with these labels
    app.kubernetes.io/name: frontend
```

**Service types:**

| Type | Access | Example |
|------|--------|---------|
| `ClusterIP` (default) | Internal only — other pods can reach it by name | All three services in this project |
| `NodePort` | Exposes on a port (30000-32767) on every node | NGINX Ingress Controller uses this |
| `LoadBalancer` | Cloud provider provisions an external load balancer | Used on AWS/GCP/Azure instead of NodePort |
| `ExternalName` | Maps to an external DNS name (CNAME) | Not used in this project |

```bash
# List services
kubectl get svc -n oncall

# Example output:
# NAME         TYPE        CLUSTER-IP      PORT(S)     AGE
# frontend     ClusterIP   10.96.45.123    80/TCP      5m
# calculator   ClusterIP   10.96.78.456    80/TCP      5m
# mongodb      ClusterIP   10.96.12.789    27017/TCP   5m

# Test a service from inside the cluster
kubectl run curl --image=curlimages/curl -it --rm -- curl http://frontend.oncall.svc.cluster.local/health
```

**How port mapping works:**

```
External → Service port (80) → targetPort (5000) → Container
                                                     │
         "port" is what other pods connect to    "targetPort" is what
          (e.g. http://frontend:80)               the app listens on
```

---

### Namespace

A Namespace is a virtual cluster within Kubernetes — it isolates resources by name. This project deploys everything into the `oncall` namespace.

```bash
# Create a namespace
kubectl create namespace oncall

# List all namespaces
kubectl get namespaces

# List resources in a specific namespace
kubectl get all -n oncall

# Common system namespaces:
# kube-system     — Kubernetes core components (API server, scheduler, etc.)
# kube-public     — Publicly readable resources
# default         — Where resources go if no namespace is specified
# ingress-nginx   — NGINX Ingress Controller
# oncall          — This application
```

---

### Ingress

An Ingress is a routing rule that maps external HTTP(S) traffic to internal Services based on hostname and/or path. It requires an Ingress Controller (like NGINX) to actually implement the routing.

**How this project uses it:** One Ingress routes `oncall-on-demand.com` to the `frontend` Service on port 80.

```yaml
# From deploy/helm/oncall-on-demand/templates/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: oncall-ingress
  namespace: oncall
spec:
  ingressClassName: nginx        # Which controller handles this Ingress
  rules:
    - host: oncall-on-demand.com # Match requests for this hostname
      http:
        paths:
          - path: /              # Match all paths
            pathType: Prefix
            backend:
              service:
                name: frontend   # Route to the frontend Service
                port:
                  number: 80     # On port 80
```

**Traffic flow with Ingress:**

```
Browser → http://oncall-on-demand.com:30080
              │
              ▼
      Node (port 30080 via NodePort)
              │
              ▼
  ┌───────────────────────────┐
  │ NGINX Ingress Controller  │  Reads Ingress resources,
  │ (pod in ingress-nginx ns) │  matches host + path
  └──────────┬────────────────┘
             │ host: oncall-on-demand.com, path: /
             ▼
  ┌──────────────────────────┐
  │ frontend Service (:80)   │ → frontend Pods (:5000)
  └──────────────────────────┘
```

**With TLS:**

```yaml
spec:
  tls:
    - secretName: oncall-tls       # K8s Secret containing TLS cert + key
      hosts:
        - oncall-on-demand.com
  rules:
    - host: oncall-on-demand.com
      # ...same as above
```

```bash
# View ingress resources
kubectl get ingress -n oncall

# Describe for detailed routing info
kubectl describe ingress oncall-ingress -n oncall
```

---

### IngressClass

An IngressClass links an Ingress resource to a specific Ingress Controller. If you have multiple controllers (e.g., NGINX + Traefik), IngressClass tells Kubernetes which one handles which Ingress.

```yaml
# Created automatically by the NGINX Ingress Controller install
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
spec:
  controller: k8s.io/ingress-nginx
```

```bash
# View IngressClasses
kubectl get ingressclass

# Example output:
# NAME    CONTROLLER                    PARAMETERS   AGE
# nginx   k8s.io/ingress-nginx          <none>       10m
```

The `ingressClassName: nginx` in the Ingress spec references this IngressClass.

---

### Ingress Controller

An Ingress Controller is a pod running a reverse proxy (NGINX, Traefik, HAProxy) that watches Ingress resources and configures routing rules dynamically. Without it, Ingress resources have no effect.

```bash
# Install NGINX Ingress Controller for bare-metal/kubeadm
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/baremetal/deploy.yaml

# The install creates:
#   - Namespace: ingress-nginx
#   - Deployment: ingress-nginx-controller (the NGINX pod)
#   - Service: ingress-nginx-controller (NodePort — exposes ports 30080/30443)
#   - IngressClass: nginx
#   - Various RBAC resources

# Check the controller is running
kubectl get pods -n ingress-nginx
kubectl get svc -n ingress-nginx
```

| Environment | Service Type | How you access it |
|-------------|-------------|-------------------|
| Bare-metal / kubeadm | NodePort | `http://<node-ip>:30080` |
| Cloud (AWS/GCP/Azure) | LoadBalancer | External IP or DNS provided automatically |
| minikube | `minikube tunnel` | `http://localhost` |

---

### PersistentVolume (PV)

A PersistentVolume is a piece of storage provisioned in the cluster. It exists independently of any Pod — data survives Pod restarts and rescheduling.

```yaml
# Manual PV example (for kubeadm without a storage provisioner)
apiVersion: v1
kind: PersistentVolume
metadata:
  name: oncall-mongodb-pv
spec:
  capacity:
    storage: 5Gi                 # How much space
  accessModes:
    - ReadWriteOnce              # One node can mount read-write
  hostPath:
    path: /data/oncall-mongodb   # Directory on the node's local disk
  claimRef:                      # Pre-bind to a specific PVC
    namespace: oncall
    name: oncall-oncall-on-demand-mongodb-data
```

**Access modes:**

| Mode | Short | Meaning |
|------|-------|---------|
| `ReadWriteOnce` | RWO | One node can mount read-write |
| `ReadOnlyMany` | ROX | Many nodes can mount read-only |
| `ReadWriteMany` | RWX | Many nodes can mount read-write (requires NFS or similar) |

```bash
# List PersistentVolumes (cluster-wide, not namespaced)
kubectl get pv

# Example output:
# NAME                 CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM
# pvc-abc123           5Gi        RWO            Delete           Bound    oncall/oncall-...-mongodb-data
```

---

### PersistentVolumeClaim (PVC)

A PVC is a **request** for storage by a Pod. It binds to a PV that matches its size and access mode. Think of PV as the actual disk and PVC as the ticket to claim it.

**How this project uses it:** One PVC for MongoDB data (5Gi, ReadWriteOnce).

```yaml
# From deploy/helm/oncall-on-demand/templates/mongodb-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: oncall-oncall-on-demand-mongodb-data
  namespace: oncall
spec:
  accessModes:
    - ReadWriteOnce              # Matches the PV's access mode
  storageClassName: local-path   # Which StorageClass to use (or "" for default)
  resources:
    requests:
      storage: 5Gi               # How much space to request
```

**The PVC is then mounted in the MongoDB Deployment:**

```yaml
# In the MongoDB Deployment pod spec:
spec:
  containers:
    - name: mongodb
      volumeMounts:
        - name: mongodb-data
          mountPath: /data/db      # MongoDB's default data directory
  volumes:
    - name: mongodb-data
      persistentVolumeClaim:
        claimName: oncall-oncall-on-demand-mongodb-data
```

```bash
# List PVCs
kubectl get pvc -n oncall

# Example output:
# NAME                                    STATUS   VOLUME       CAPACITY   ACCESS MODES   STORAGECLASS
# oncall-oncall-on-demand-mongodb-data    Bound    pvc-abc123   5Gi        RWO            local-path

# If PVC is stuck in Pending, check events:
kubectl describe pvc oncall-oncall-on-demand-mongodb-data -n oncall
```

**PV vs PVC lifecycle:**

```
1. PVC created (requests 5Gi, RWO)
       │
       ▼
2. StorageClass provisioner creates a PV (or you create one manually)
       │
       ▼
3. PVC binds to PV (status: Bound)
       │
       ▼
4. Pod mounts the PVC as a volume
       │
       ▼
5. Pod writes data to /data/db → stored on the PV's disk
       │
       ▼
6. Pod is deleted → PVC and PV remain → data persists
```

---

### StorageClass

A StorageClass defines **how** PersistentVolumes are provisioned. It tells Kubernetes which provisioner to use and what parameters to apply (disk type, speed, replication, etc.).

**How this project uses it:** `values.yaml` defaults to `storageClassName: ""` (use cluster default). On kubeadm, you install `local-path-provisioner` to provide a default StorageClass.

```yaml
# The local-path StorageClass (installed by local-path-provisioner)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-path
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"  # Makes this the default
provisioner: rancher.io/local-path
reclaimPolicy: Delete           # Delete the PV when PVC is deleted
volumeBindingMode: WaitForFirstConsumer  # Create PV only when a Pod needs it
```

**Common StorageClasses by environment:**

| Environment | StorageClass | Provisioner | Backing storage |
|-------------|-------------|-------------|-----------------|
| kubeadm (single-node) | `local-path` | rancher.io/local-path | Local disk (`/opt/local-path-provisioner/`) |
| AWS EKS | `gp3` | ebs.csi.aws.com | EBS volumes |
| GCP GKE | `standard` | pd.csi.storage.gke.io | Persistent Disks |
| Azure AKS | `managed-premium` | disk.csi.azure.com | Managed Disks |
| k3s | `local-path` | rancher.io/local-path | Pre-installed |

```bash
# List StorageClasses
kubectl get storageclass

# Make local-path the default
kubectl patch storageclass local-path -p \
  '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

**Reclaim policies:**

| Policy | Behavior |
|--------|----------|
| `Delete` | PV and its data are deleted when PVC is deleted (default for dynamic provisioning) |
| `Retain` | PV is kept after PVC deletion — admin must manually reclaim |

---

### Secret

A Secret stores sensitive data (passwords, API keys, TLS certificates) in base64-encoded form. Pods reference Secrets through environment variables or volume mounts.

**How this project uses it:** One Secret stores the Flask session secret key.

```yaml
# From deploy/helm/oncall-on-demand/templates/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: oncall-oncall-on-demand-secrets
  namespace: oncall
type: Opaque
data:
  flask-secret-key: Y2hhbmdlLW1lLWluLXByb2R1Y3Rpb24=  # base64 of "change-me-in-production"
```

**Referencing a Secret in a Deployment:**

```yaml
env:
  - name: SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: oncall-oncall-on-demand-secrets
        key: flask-secret-key    # Decoded automatically at runtime
```

```bash
# List secrets
kubectl get secrets -n oncall

# View a secret's contents (base64 encoded)
kubectl get secret oncall-oncall-on-demand-secrets -n oncall -o yaml

# Decode a specific key
kubectl get secret oncall-oncall-on-demand-secrets -n oncall \
  -o jsonpath='{.data.flask-secret-key}' | base64 -d

# Create a secret from the command line
kubectl create secret generic my-secret \
  --from-literal=password=s3cret \
  -n oncall
```

> **Important:** base64 is encoding, not encryption. Secrets are stored in etcd in plain text
> by default. For production, enable [encryption at rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/).

---

### ConfigMap

A ConfigMap stores non-sensitive configuration data as key-value pairs. Similar to Secrets but for non-sensitive data. This project passes config via environment variables in the Deployment spec instead, but ConfigMaps are a common alternative.

```yaml
# Example ConfigMap (not used in this project, shown for reference)
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: oncall
data:
  MONGO_URI: "mongodb://mongodb:27017"
  DB_NAME: "oncall_db"
  LOG_LEVEL: "INFO"
```

```yaml
# Referencing a ConfigMap in a Deployment:
env:
  - name: MONGO_URI
    valueFrom:
      configMapKeyRef:
        name: app-config
        key: MONGO_URI

# Or mount all keys as a file:
volumes:
  - name: config
    configMap:
      name: app-config
```

```bash
# Create a ConfigMap
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=DEBUG \
  -n oncall

# View contents
kubectl get configmap app-config -n oncall -o yaml
```

---

### ServiceAccount

A ServiceAccount provides an identity for Pods to interact with the Kubernetes API. Every Pod runs under a ServiceAccount (default: `default`).

**How this project uses it:** One shared ServiceAccount for all pods.

```yaml
# From deploy/helm/oncall-on-demand/templates/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: oncall-oncall-on-demand
  namespace: oncall
```

```yaml
# Referenced in each Deployment:
spec:
  serviceAccountName: oncall-oncall-on-demand
```

```bash
# List service accounts
kubectl get serviceaccounts -n oncall
```

---

### NetworkPolicy

A NetworkPolicy controls which Pods can talk to which other Pods (and external endpoints). By default, all Pods can communicate freely. NetworkPolicies restrict this.

**Requires a CNI that supports NetworkPolicy** (Calico, Cilium). Flannel does NOT enforce them.

**How this project uses it:** Three NetworkPolicies isolate traffic between components.

```yaml
# Frontend NetworkPolicy — allows ingress from anywhere, egress only to calculator + mongodb + DNS
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: oncall-frontend
  namespace: oncall
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: frontend      # Applies to frontend pods
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - ports:
        - port: 5000                         # Accept traffic on port 5000 from anyone
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: mongodb
      ports:
        - port: 27017                        # Allow egress to MongoDB
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: calculator
      ports:
        - port: 5001                         # Allow egress to Calculator
    - to:
        - namespaceSelector: {}              # Allow DNS resolution (any namespace)
      ports:
        - port: 53
          protocol: UDP
        - port: 53
          protocol: TCP
```

**Traffic matrix for this project:**

```
                    ┌──────────┐  ┌────────────┐  ┌─────────┐
                    │ Frontend │  │ Calculator │  │ MongoDB │
                    └──────────┘  └────────────┘  └─────────┘
From Frontend    →      —            ✓ (5001)      ✓ (27017)
From Calculator  →      ✗                —         ✓ (27017)
From MongoDB     →      ✗               ✗              —
From Ingress     →   ✓ (5000)           ✗              ✗
```

```bash
# List network policies
kubectl get networkpolicy -n oncall

# Describe a specific policy
kubectl describe networkpolicy oncall-frontend -n oncall
```

---

### Labels and Selectors

Labels are key-value pairs attached to Kubernetes objects. Selectors filter objects by their labels. Almost every Kubernetes resource uses them.

**How this project uses them:**

```yaml
# Labels on a pod (set in the Deployment template):
metadata:
  labels:
    app.kubernetes.io/name: frontend        # Component name
    app.kubernetes.io/instance: oncall       # Helm release name
    app.kubernetes.io/version: "1.0.0"      # App version
    app.kubernetes.io/managed-by: Helm       # Managed by Helm
    app.kubernetes.io/part-of: oncall-on-demand  # Part of this application
    app.kubernetes.io/component: frontend    # Specific component
```

```yaml
# A Service selector — routes traffic to pods matching these labels:
spec:
  selector:
    app.kubernetes.io/name: frontend
    app.kubernetes.io/instance: oncall
```

```bash
# List pods with a specific label
kubectl get pods -n oncall -l app.kubernetes.io/name=frontend

# Show all labels on pods
kubectl get pods -n oncall --show-labels

# Filter by multiple labels
kubectl get pods -n oncall -l "app.kubernetes.io/name=frontend,app.kubernetes.io/instance=oncall"
```

---

### Annotations

Annotations are key-value metadata on Kubernetes objects, similar to labels but not used for selection. They store non-identifying information for tools, controllers, and humans.

**Common Ingress annotations (NGINX):**

```yaml
# Examples you can add to values.yaml → ingress.annotations:
ingress:
  annotations:
    # Rate limiting
    nginx.ingress.kubernetes.io/limit-rps: "10"

    # Redirect HTTP to HTTPS
    nginx.ingress.kubernetes.io/ssl-redirect: "true"

    # Custom timeout
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"

    # CORS
    nginx.ingress.kubernetes.io/enable-cors: "true"

    # URL rewrite
    nginx.ingress.kubernetes.io/rewrite-target: /
```

```yaml
# StorageClass annotation — marks it as the cluster default:
metadata:
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
```

**Labels vs Annotations:**

| | Labels | Annotations |
|--|--------|-------------|
| **Purpose** | Identify and select objects | Store metadata for tools and humans |
| **Used by selectors** | Yes | No |
| **Size limit** | 63 chars per value | 256 KB total |
| **Example** | `app.kubernetes.io/name: frontend` | `nginx.ingress.kubernetes.io/limit-rps: "10"` |

```bash
# View annotations on an ingress
kubectl get ingress oncall-ingress -n oncall -o jsonpath='{.metadata.annotations}'

# Add an annotation
kubectl annotate ingress oncall-ingress -n oncall \
  nginx.ingress.kubernetes.io/limit-rps="10"
```

---

### Init Containers

An init container runs **before** the main container starts. It must complete successfully before the main container is started. Used for setup tasks, waiting for dependencies, or running migrations.

**How this project uses it:** Frontend and Calculator Deployments have init containers that wait for MongoDB to be reachable before starting the app.

```yaml
# From the frontend Deployment:
initContainers:
  - name: wait-for-mongodb
    image: busybox:1.36
    command:
      - sh
      - -c
      - |
        echo "Waiting for MongoDB at mongodb:27017..."
        until nc -z mongodb 27017; do
          echo "MongoDB not ready — sleeping 3s"
          sleep 3
        done
        echo "MongoDB is reachable"
```

**Init container vs main container:**

| | Init Container | Main Container |
|--|---------------|----------------|
| **Runs** | Once, before main container | Continuously |
| **Must succeed** | Yes — pod won't start otherwise | Restarts based on `restartPolicy` |
| **Use case** | Wait for deps, run migrations, download config | Run the application |

```bash
# View init container logs
kubectl logs <pod-name> -n oncall -c wait-for-mongodb

# If a pod is stuck in "Init:0/1", the init container hasn't completed
kubectl describe pod <pod-name> -n oncall
```

---

### Probes (Liveness and Readiness)

Probes let Kubernetes monitor the health of your containers and take automatic action.

**How this project uses them:** All three Deployments define both liveness and readiness probes.

```yaml
# From the frontend Deployment:
livenessProbe:                    # "Is the container alive?"
  httpGet:
    path: /health                 # Calls GET /health on the container
    port: http
  initialDelaySeconds: 15         # Wait 15s after start before first check
  periodSeconds: 20               # Check every 20s
  timeoutSeconds: 5               # Fail if no response in 5s
  failureThreshold: 3             # Kill container after 3 consecutive failures

readinessProbe:                   # "Is the container ready for traffic?"
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 5          # Wait 5s before first check
  periodSeconds: 10               # Check every 10s
  timeoutSeconds: 5
  failureThreshold: 3             # Remove from Service after 3 failures
```

```yaml
# MongoDB uses exec probes instead of HTTP:
livenessProbe:
  exec:
    command:
      - mongosh
      - --eval
      - "db.adminCommand('ping')"
```

**Probe types:**

| Probe | Question it answers | Action on failure |
|-------|-------------------|-------------------|
| **Liveness** | "Is the container alive?" | Restart the container |
| **Readiness** | "Can it accept traffic?" | Remove from Service endpoints (no traffic) |
| **Startup** | "Has it finished starting?" | Block liveness/readiness until success |

**Check methods:**

| Method | Example | Used by |
|--------|---------|---------|
| `httpGet` | `GET /health` on port 5000 | Frontend, Calculator |
| `exec` | Run `mongosh --eval "db.adminCommand('ping')"` | MongoDB |
| `tcpSocket` | Try to open a TCP connection | Not used in this project |

---

### Resource Requests and Limits

Resource requests and limits control how much CPU and memory a container can use. Requests are guaranteed minimums; limits are hard maximums.

**How this project uses them:**

```yaml
# From values.yaml:
frontend:
  resources:
    requests:
      cpu: 100m          # Guaranteed 0.1 CPU cores
      memory: 128Mi      # Guaranteed 128 MB RAM
    limits:
      cpu: 250m          # Maximum 0.25 CPU cores
      memory: 256Mi      # Maximum 256 MB RAM (OOMKilled if exceeded)
```

**Units:**

| Unit | Meaning | Example |
|------|---------|---------|
| `m` (millicores) | 1/1000 of a CPU core | `100m` = 0.1 cores |
| `Mi` (mebibytes) | 1,048,576 bytes | `128Mi` = 134 MB |
| `Gi` (gibibytes) | 1,073,741,824 bytes | `5Gi` = 5.4 GB |

```bash
# View resource usage (requires metrics-server)
kubectl top pods -n oncall

# View requests/limits for a pod
kubectl describe pod <pod-name> -n oncall | grep -A 5 "Requests\|Limits"
```

---

### Helm Concepts

Helm is a package manager for Kubernetes. It bundles Kubernetes manifests into reusable **charts**, supports templating, and manages release lifecycle (install, upgrade, rollback).

**Chart structure for this project:**

```
deploy/helm/oncall-on-demand/
├── Chart.yaml              # Chart metadata (name, version, description)
├── values.yaml             # Default configuration values
└── templates/              # Kubernetes manifest templates
    ├── _helpers.tpl         # Reusable template functions
    ├── NOTES.txt            # Post-install message
    ├── frontend-deployment.yaml
    ├── frontend-service.yaml
    ├── calculator-deployment.yaml
    ├── calculator-service.yaml
    ├── mongodb-deployment.yaml
    ├── mongodb-service.yaml
    ├── mongodb-pvc.yaml
    ├── secrets.yaml
    ├── serviceaccount.yaml
    ├── ingress.yaml
    └── networkpolicy.yaml
```

**Key Helm concepts:**

| Concept | Description | Example |
|---------|-------------|---------|
| **Chart** | A package of templated K8s manifests | `deploy/helm/oncall-on-demand/` |
| **Release** | An installed instance of a chart | `helm install oncall ...` creates release "oncall" |
| **values.yaml** | Default config — overridable via `--set` or `-f` | `frontend.replicaCount: 2` |
| **Templates** | Go/Sprig templates generating YAML | `{{ .Values.frontend.image.tag }}` renders to `1.0.0` |
| **_helpers.tpl** | Shared template functions (DRY) | `{{ include "oncall.fullname" . }}` renders to `oncall-oncall-on-demand` |
| **NOTES.txt** | Message shown after `helm install` | Shows access URLs and credentials |

**Template syntax examples from this project:**

```yaml
# Simple value substitution:
replicas: {{ .Values.frontend.replicaCount }}          # renders to: replicas: 2

# Quoted value:
value: {{ .Values.global.mongodb.uri | quote }}        # renders to: value: "mongodb://mongodb:27017"

# Include a helper function:
name: {{ include "oncall.fullname" . }}-frontend       # renders to: name: oncall-oncall-on-demand-frontend

# Conditional block:
{{- if .Values.ingress.enabled }}
  # ...Ingress resource rendered only if enabled
{{- end }}

# Loop:
{{- range .Values.ingress.tls }}
- secretName: {{ .secretName }}
{{- end }}

# Base64 encoding (for Secrets):
flask-secret-key: {{ .Values.frontend.env.secretKey | b64enc | quote }}

# YAML block insertion with indent:
resources:
  {{- toYaml .Values.frontend.resources | nindent 12 }}
```

```bash
# Install a chart
helm install oncall deploy/helm/oncall-on-demand/ --namespace oncall --create-namespace

# Override values at install time
helm install oncall deploy/helm/oncall-on-demand/ \
  --set frontend.replicaCount=3 \
  --set frontend.image.tag=2.0.0

# Override with a custom values file
helm install oncall deploy/helm/oncall-on-demand/ -f my-values.yaml

# Preview what will be generated (dry-run, no install)
helm template oncall deploy/helm/oncall-on-demand/ --namespace oncall

# Upgrade an existing release
helm upgrade oncall deploy/helm/oncall-on-demand/ --namespace oncall --reuse-values

# Rollback to previous version
helm rollback oncall -n oncall

# View release history
helm history oncall -n oncall

# Uninstall
helm uninstall oncall -n oncall

# List all releases across namespaces
helm list -A
```

---

### NodePort

NodePort is a Service type that exposes a port (30000-32767) on every node in the cluster. External traffic reaches the Service through `<node-ip>:<node-port>`.

**How this project uses it:** The NGINX Ingress Controller is exposed via NodePort. The application Services themselves use ClusterIP (internal only).

```bash
# The ingress controller's NodePort service:
kubectl get svc -n ingress-nginx ingress-nginx-controller

# NAME                       TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)                      AGE
# ingress-nginx-controller   NodePort   10.96.x.x      <none>        80:30080/TCP,443:30443/TCP   ...
#                                                                       ▲
#                                                                NodePort 30080
```

```
External traffic path:
  Browser → <node-ip>:30080 → NodePort Service → Ingress Controller Pod → Ingress rules → Frontend Service → Frontend Pod
```

---

### kubectl Quick Reference

Common commands used with this project:

```bash
# ── Cluster info ──
kubectl cluster-info                          # API server and CoreDNS endpoints
kubectl get nodes -o wide                     # Node status, IP, OS, container runtime
kubectl version                               # Client and server versions

# ── Viewing resources ──
kubectl get all -n oncall                     # All resources in the namespace
kubectl get pods,svc,deploy,ingress -n oncall # Specific resource types
kubectl describe <resource> <name> -n oncall  # Detailed info + events
kubectl get <resource> -o yaml -n oncall      # Full YAML definition
kubectl get <resource> -o json -n oncall      # Full JSON definition

# ── Logs ──
kubectl logs <pod> -n oncall                  # Current logs
kubectl logs <pod> -n oncall -f               # Stream logs (follow)
kubectl logs <pod> -n oncall --previous       # Logs from previous crash
kubectl logs <pod> -n oncall -c <container>   # Specific container (init or sidecar)

# ── Debugging ──
kubectl exec -it <pod> -n oncall -- /bin/sh   # Shell into a pod
kubectl port-forward svc/frontend 8080:80 -n oncall  # Local access
kubectl top pods -n oncall                    # CPU/memory (needs metrics-server)
kubectl get events -n oncall --sort-by='.lastTimestamp'  # Recent events
```

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

> If you don't have a full Kubernetes cluster, you can use **minikube** or **k3s** for single-node testing:
>
> ```bash
> # Option A: minikube
> curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
> sudo install minikube-linux-amd64 /usr/local/bin/minikube
> minikube start
>
> # Option B: k3s (lightweight)
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

# NutriPod — Deployment & Container Orchestration Guide

This document specifies the deployment architecture, container orchestration workflows, Kubernetes production configuration, and cloud provisioning strategy for the **NutriPod** multi-service platform.

---

## 1. Architectural Overview & Deployment Tiers

NutriPod operates on a dual-tier deployment model:

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                  LOCAL RUNTIME (DOCKER / PODMAN)                                 |
|                             100% Functional Local Development & Assessment                       |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|  Bridge Network: foodflow-net                                                                    |
|  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐                       |
|  │ frontend (:5173)    │  │ profile-service:8001│  │ recipe-service:8002 │                       |
|  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘                       |
|             │                        │                        │                                  |
|  ┌─────────────────────┐  ┌─────────────────────┐             │                                  |
|  │ planner-service:8003│  │ postgres (:5432)    │             │                                  |
|  └─────────────────────┘  └─────────────────────┘             │                                  |
|             │                        │                        │                                  |
|             ▼                        ▼                        ▼                                  |
|     [Internal REST]        [Persistent Volume: foodflow-db-data]                                 |
+──────────────────────────────────────────────────────────────────────────────────────────────────+

                                             │
                       MAPPED ARCHITECTURAL REFERENCE TO CLOUD
                                             │
                                             ▼
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                 CLOUD REFERENCE ARCHITECTURE                                     |
|                       OpenStack Magnum Provisioned Kubernetes Cluster                            |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|  KUBERNETES LAYER (k8s/ Manifests):                                                             |
|  • Ingress Controller (Ingress routing traffic to frontend and microservices)                    |
|  • Frontend Deployment & Service (React + Vite static Nginx server)                              |
|  • Microservices Deployments (FastAPI Profile, Recipe, and Planner Pods)                         |
|  • PostgreSQL StatefulSet + PVC (Cinder CSI StorageClass)                                        |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|  INFRASTRUCTURE PROVISIONING (OpenStack Magnum):                                                 |
|  • Magnum coordinates Heat to stand up Kubernetes Master & Worker Nodes                          |
|  • Keystone: Authentication, multi-tenant RBAC, service token validation                         |
|  • Nova: Compute instances (VMs) running Kubernetes nodes                                        |
|  • Heat: Template orchestration executing Magnum cluster templates                               |
|  • Neutron: Virtual SDN network, subnets, security groups, floating IPs                          |
|  • Octavia: Layer 4 / Layer 7 Load Balancing for external cluster ingress                        |
|  • Glance: Base VM operating system disk images (.qcow2 for node VMs)                            |
|  • Cinder: Persistent block volumes attached to Nova VMs for Kubernetes PVCs                     |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Local Container Orchestration (`docker-compose.yml`)

### 2.1 Service Topology & Port Allocation

| Service Container | Image / Dockerfile | Host Port | Internal Port | Network Alias |
|---|---|---|---|---|
| `foodflow-postgres` | `postgres:16-alpine` | `5432` | `5432` | `postgres` |
| `foodflow-profile-service` | `services/profile_nutrition/Dockerfile` | `8001` | `8001` | `profile-service`, `profile-nutrition` |
| `foodflow-recipe-service` | `services/recipe_ingredient/Dockerfile` | `8002` | `8002` | `recipe-service`, `recipe-ingredient` |
| `foodflow-planner-service` | `services/recommendation_planner/Dockerfile` | `8003` | `8003` | `planner-service`, `recommendation-planner` |
| `foodflow-frontend` | `frontend/Dockerfile` | `5173` | `80` | `frontend` |

### 2.2 Dual-Tier Networking Scheme

1. **Browser to Backend**: The user's web browser runs on the host machine. The React frontend interacts with the FastAPI services using host-resolvable URLs:
   - Profile & Nutrition: `http://localhost:8001`
   - Recipe & Ingredient: `http://localhost:8002`
   - Recommendation & Planner: `http://localhost:8003`
2. **Backend to Backend (Internal Network)**: Microservices communicate over the bridge network `foodflow-net` using internal container DNS names:
   - `RECIPE_SERVICE_URL=http://recipe-service:8002`
   - `PROFILE_SERVICE_URL=http://profile-service:8001`
   - `POSTGRES_HOST=postgres` (port `5432`)

### 2.3 Volume Persistence & Isolation

- **Named Volume**: `foodflow-db-data` mounts to `/var/lib/postgresql/data`. Database contents (50,000 recipes, 443,755 ingredients, 7,793 USDA foods) persist across container stops and builds.
- **Strict Prohibition**: Never execute `docker compose down -v` in production or assessment environments, as this drops the persistent database volume.

### 2.4 Quickstart Commands

```bash
# Build all container images without starting
docker compose build

# Start the full stack in detached mode
docker compose up -d

# Inspect health and status of all containers
docker compose ps

# View real-time logs for a specific service
docker compose logs -f profile-service
docker compose logs -f recipe-service
docker compose logs -f planner-service
docker compose logs -f frontend

# Gracefully stop the application while preserving database volume
docker compose stop
# or
docker compose down
```

---

## 3. Security & Container Hardening

1. **Non-Root Execution**:
   - Backend Python containers define and run as unprivileged user `foodflow` (`uid=10001`, `gid=10001`).
   - Root privileges are dropped immediately after package installation.
2. **Least-Privilege Database Roles**:
   - `foodflow_profile_user`: Only has `SELECT`, `INSERT`, `UPDATE`, `DELETE` on schema `profile_nutrition`. Cross-schema queries to `recipe_catalog` or `meal_planner` are blocked at the engine level.
   - `foodflow_recipe_user`: Only has privileges on schema `recipe_catalog`.
   - `foodflow_planner_user`: Only has privileges on schema `meal_planner`.
   - Administrative operations (`foodflow_admin`) are reserved for migrations and dataset seeders.
3. **CORS Restrictions**:
   - FastAPI services configure `CORSMiddleware` with explicit origin whitelist (`http://localhost:5173`, `http://127.0.0.1:5173`).
   - Credentials are not leaked; wildcard `*` origins are forbidden.

---

## 4. Kubernetes Manifest Suite (`k8s/`)

The declarative manifests in `k8s/` provide a production-grade Kubernetes topology:

```text
k8s/
├── namespace.yaml                  # Dedicated namespace: foodflow
├── config/
│   ├── configmap.yaml              # Non-sensitive runtime environment variables
│   └── secret.yaml                 # Template for cluster secrets (NEVER commit live secrets)
├── storage/
│   └── postgres-pvc.yaml           # PersistentVolumeClaim (Cinder CSI StorageClass)
├── statefulsets/
│   └── postgres-statefulset.yaml   # PostgreSQL 16 StatefulSet with mounted volume
├── deployments/
│   ├── profile-deployment.yaml     # Profile & Nutrition Service (FastAPI)
│   ├── recipe-deployment.yaml      # Recipe & Ingredient Service (FastAPI)
│   ├── planner-deployment.yaml     # Recommendation & Planner Service (FastAPI)
│   └── frontend-deployment.yaml    # React SPA served via Nginx
├── services/
│   ├── postgres-service.yaml       # ClusterIP (port 5432)
│   ├── profile-service.yaml        # ClusterIP (port 8001)
│   ├── recipe-service.yaml         # ClusterIP (port 8002)
│   ├── planner-service.yaml        # ClusterIP (port 8003)
│   └── frontend-service.yaml       # ClusterIP (port 80)
└── ingress/
    └── foodflow-ingress.yaml       # Ingress path routing to frontend and microservice APIs
```

### Applying Manifests to a Kubernetes Cluster

```bash
# 1. Create dedicated namespace
kubectl apply -f k8s/namespace.yaml

# 2. Deploy configuration & secrets
kubectl apply -f k8s/config/configmap.yaml
kubectl apply -f k8s/config/secret.yaml

# 3. Provision storage & database statefulset
kubectl apply -f k8s/storage/postgres-pvc.yaml
kubectl apply -f k8s/services/postgres-service.yaml
kubectl apply -f k8s/statefulsets/postgres-statefulset.yaml

# 4. Deploy backend microservices
kubectl apply -f k8s/deployments/profile-deployment.yaml
kubectl apply -f k8s/services/profile-service.yaml

kubectl apply -f k8s/deployments/recipe-deployment.yaml
kubectl apply -f k8s/services/recipe-service.yaml

kubectl apply -f k8s/deployments/planner-deployment.yaml
kubectl apply -f k8s/services/planner-service.yaml

# 5. Deploy frontend static server & ingress
kubectl apply -f k8s/deployments/frontend-deployment.yaml
kubectl apply -f k8s/services/frontend-service.yaml
kubectl apply -f k8s/ingress/foodflow-ingress.yaml
```

---

## 5. OpenStack Magnum Cloud Architecture Reference

### 5.1 OpenStack Core Services Interplay

In an OpenStack cloud environment, the following core services collaborate to provision and manage the infrastructure hosting NutriPod:

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    OPENSTACK CORE SERVICES                                       |
+─────────────┬──────────────────────────┬─────────────────────────────────────────────────────────+
| SERVICE     | FUNCTIONAL DOMAIN        | ROLE IN NUTRIPOD CLUSTER LIFECYCLE                      |
+─────────────┼──────────────────────────┼─────────────────────────────────────────────────────────+
| **Keystone**| Identity & Access        | Authenticates Magnum CLI/API requests; validates tenant |
|             | Management (IAM)         | credentials; provides service tokens for Heat & Nova.   |
+─────────────┼──────────────────────────┼─────────────────────────────────────────────────────────+
| **Nova**    | Compute Virtualization   | Boots and manages the virtual machines that function as |
|             | (Hypervisor Management)  | Kubernetes Control Plane and Worker nodes.              |
+─────────────┼──────────────────────────┼─────────────────────────────────────────────────────────+
| **Neutron** | Software-Defined         | Provisions virtual tenant networks, subnets, routers,   |
|             | Networking (SDN)         | security groups, and floating IPs for cluster nodes.    |
+─────────────┼──────────────────────────┼─────────────────────────────────────────────────────────+
| **Octavia** | Load Balancing as a      | Provisions Layer 4 / Layer 7 load balancers to route    |
|             | Service (LBaaS)          | external internet traffic to the Kubernetes Ingress.    |
+─────────────┼──────────────────────────┼─────────────────────────────────────────────────────────+
| **Glance**  | VM Image Registry        | Stores immutable base operating system disk images      |
|             | (Machine Images)         | (e.g. Fedora CoreOS .qcow2) used to boot cluster VMs.   |
+─────────────┼──────────────────────────┼─────────────────────────────────────────────────────────+
| **Cinder**  | Block Storage            | Provides persistent block storage volumes; interfaces   |
|             | (Block Volumes)          | with K8s Cinder CSI driver for database persistence.    |
+─────────────┼──────────────────────────┼─────────────────────────────────────────────────────────+
| **Heat**    | Orchestration Engine     | Executes OpenStack Heat Orchestration Templates (HOT)   |
|             | (Template Engine)        | generated by Magnum to orchestrate Nova, Neutron, Cinder|
+─────────────┼──────────────────────────┼─────────────────────────────────────────────────────────+
| **Magnum**  | Container Infrastructure | High-level API coordinating Heat to provision certified|
|             | Management (COE)         | Kubernetes clusters on OpenStack infrastructure.         |
+─────────────┼──────────────────────────┼─────────────────────────────────────────────────────────+
```

### 5.2 Strict Architectural Distinction: Glance VM Images vs. Application Container Images

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                            VIRTUAL MACHINE IMAGE VS. CONTAINER IMAGE                             |
+────────────────────────────────────────────────┬─────────────────────────────────────────────────+
| OPENSTACK GLANCE VM IMAGE                      | APPLICATION CONTAINER IMAGE (OCI)               |
+────────────────────────────────────────────────┼─────────────────────────────────────────────────+
| • Stored in OpenStack Glance                   | • Stored in OCI Container Registry (Hub/Harbor) |
| • Complete Virtual Machine Disk Image          | • Lightweight Application Filesystem Layers     |
| • Format: .qcow2, .raw, .vmdk                  | • Format: OCI Image / Docker Image Spec         |
| • Contains full OS, Linux Kernel, systemd,     | • Contains ONLY application runtime (Python,    |
|   cloud-init, and container runtime engine     |   Node.js), libraries, and application code     |
| • Consumed by: Nova compute hypervisors        | • Consumed by: Container engine (CRI-O / Podman)|
| • Used to boot K8s master & worker node VMs    | • Used to instantiate application Pods in K8s   |
| • Infrastructure layer (Managed by Ops/Magnum) | • Application layer (Built by NutriPod team)    |
+────────────────────────────────────────────────┴─────────────────────────────────────────────────+
```

> **Critical Rule**: NutriPod application containers are packaged as OCI images via `docker build` / `podman build` and pushed to an OCI registry (e.g., GitHub Container Registry, Harbor, Docker Hub). They are **never** uploaded to OpenStack Glance. Glance is strictly reserved for the operating system images used to boot the cluster node virtual machines.

### 5.3 Magnum Cluster Provisioning Workflow (Architectural Reference)

```bash
# Step 1: Create a Magnum Cluster Template
openstack coe cluster template create foodflow-k8s-template \
    --image fedora-coreos-38 \
    --keypair foodflow-key \
    --external-network public \
    --dns-nameserver 8.8.8.8 \
    --flavor m1.medium \
    --master-flavor m1.medium \
    --network-driver flannel \
    --volume-driver cinder \
    --docker-storage-driver overlay2 \
    --coe kubernetes

# Step 2: Instantiate the Kubernetes Cluster
openstack coe cluster create foodflow-cluster \
    --cluster-template foodflow-k8s-template \
    --master-count 1 \
    --node-count 3

# Step 3: Retrieve Cluster Credentials & Configure kubectl
openstack coe cluster config foodflow-cluster --dir ~/.kube

# Step 4: Verify Cluster Nodes
kubectl get nodes
```

---

## 6. Health Checks, Monitoring & Diagnostics

### 6.1 Service Health Probes

Each microservice exposes an RFC-compliant HTTP health endpoint returning database connection status and schema verification:

- `GET http://localhost:8001/health` $\rightarrow$ Checks `profile_nutrition` schema and `usda_foods` probe.
- `GET http://localhost:8002/health` $\rightarrow$ Checks `recipe_catalog` schema and `recipes` probe.
- `GET http://localhost:8003/health` $\rightarrow$ Checks `meal_planner` schema and `guest_sessions` probe.
- `GET http://localhost:5173/healthz` $\rightarrow$ Checks Nginx web server responsiveness.

### 6.2 Common Troubleshooting Actions

1. **Service container reports unhealthy on startup**:
   - Inspect PostgreSQL connectivity: `docker compose exec postgres pg_isready -U foodflow_admin -d foodflow_db`.
   - Verify that all three database roles exist and passwords in `.env` match.
2. **CORS errors when browsing frontend**:
   - Ensure the browser accesses `http://localhost:5173` (matching the allowed origins in `CORS_ORIGINS`).
3. **Pantry or Planner cannot reach Recipe Service**:
   - Verify `RECIPE_SERVICE_URL=http://recipe-service:8002` is set in the container environment.
   - Run `docker compose exec planner-service curl -s http://recipe-service:8002/health`.


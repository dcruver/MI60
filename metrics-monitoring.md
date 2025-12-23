# Metrics and Monitoring

Prometheus metrics and Grafana dashboards for GPU health and state monitoring.

## Prometheus Metrics

The `gpu-state-service` exposes Prometheus metrics on port 9100:

```
# GPU state and configuration
gpu_config_info{config="big-chat",model="llama-3.3-70b"} 1
gpu_state_info{state="ready"} 1
gpu_ready 1
gpu_config_switches_total 5
gpu_config_uptime_seconds 3600

# Temperature monitoring (from separate AMD GPU exporter on port 9101)
amd_gpu_temperature_junction_celsius{gpu="0"} 72
amd_gpu_temperature_junction_celsius{gpu="1"} 75
amd_gpu_utilization_percent{gpu="0"} 85
amd_gpu_power_watts{gpu="0"} 180
```

## Prometheus Endpoints

| Port | Service | Metrics |
|------|---------|---------|
| 9100 | gpu-state-service | Config state, switches, uptime |
| 9101 | AMD GPU exporter | Temperature, utilization, power |
| 9102 | NVIDIA GPU exporter | RTX 2080 metrics (if present) |

## Temperature Alerts

The service monitors junction temperatures and sends ntfy notifications:

| Threshold | Level | Action |
|-----------|-------|--------|
| 97°C | Warning | Notification sent |
| 100°C | High | Notification sent |
| 105°C | Critical | Notification sent |
| 110°C | Emergency | Notification sent |

Notifications are sent to the configured ntfy topic when thresholds are crossed.

## Grafana Dashboard

A Grafana dashboard (`Feynman GPUs`) displays:

- Current configuration and loaded model
- GPU state (ready/loading/switching)
- Junction temperatures with threshold lines
- GPU utilization (compute and memory)
- Power draw across all GPUs
- Configuration timeline showing when switches occurred

## Prometheus Scrape Configuration

Add these targets to your Prometheus configuration:

```yaml
scrape_configs:
  - job_name: 'feynman-gpu-state'
    static_configs:
      - targets: ['192.168.1.131:9100']
        labels:
          host: feynman

  - job_name: 'feynman-amd-gpu'
    static_configs:
      - targets: ['192.168.1.131:9101']
        labels:
          host: feynman

  - job_name: 'feynman-nvidia-gpu'
    static_configs:
      - targets: ['192.168.1.131:9102']
        labels:
          host: feynman
```

## Example Queries

### Current Configuration
```promql
gpu_config_info
```

### GPU Temperature Over Time
```promql
amd_gpu_temperature_junction_celsius{gpu="0"}
amd_gpu_temperature_junction_celsius{gpu="1"}
```

### Average GPU Utilization (last 5 minutes)
```promql
avg_over_time(amd_gpu_utilization_percent[5m])
```

### Configuration Switch Rate
```promql
rate(gpu_config_switches_total[1h])
```

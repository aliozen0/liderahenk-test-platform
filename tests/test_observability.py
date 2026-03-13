"""
Gözlemlenebilirlik Testi — LiderAhenk Test Platform
Prometheus → Grafana veri pipeline'ını uçtan uca test eder.
Grafana'da "No Data" sorununun kökenini bulur.

Kullanım:
    PYTHONPATH=. pytest tests/test_observability.py -v --timeout=30
"""
import pytest
import requests


# ─── Yardımcı fonksiyonlar ─────────────────────────────────────────

def http_get(url, timeout=5, **kwargs):
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


PROM = "http://127.0.0.1:9090"
GRAFANA = "http://127.0.0.1:3000"
GRAFANA_AUTH = ("admin", "admin")


# ─── Prometheus Testleri ───────────────────────────────────────────

class TestPrometheus:
    """Prometheus'un çalışma durumu ve target'ları."""

    def test_prometheus_ready(self):
        """Prometheus hazır olmalı."""
        resp = http_get(f"{PROM}/-/ready")
        assert resp and resp.status_code == 200, "Prometheus erişilemez"

    def test_prometheus_config_loaded(self):
        """Prometheus konfigürasyonu yüklenmiş olmalı."""
        resp = http_get(f"{PROM}/api/v1/status/config")
        assert resp and resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success", "Prometheus config yüklenemedi"

    def test_prometheus_targets_exist(self):
        """Prometheus'ta en az 1 scrape target tanımlı olmalı."""
        resp = http_get(f"{PROM}/api/v1/targets")
        assert resp and resp.status_code == 200
        data = resp.json()
        targets = data.get("data", {}).get("activeTargets", [])
        assert len(targets) > 0, "Hiç aktif target yok"

    @pytest.mark.parametrize("job_name", [
        "cadvisor",
        "mariadb",
        "liderapi",
        "ejabberd",
        "lider-core",
    ])
    def test_prometheus_target_configured(self, job_name):
        """Her beklenen job target olarak tanımlı olmalı."""
        resp = http_get(f"{PROM}/api/v1/targets")
        assert resp and resp.status_code == 200
        targets = resp.json().get("data", {}).get("activeTargets", [])
        job_names = [t.get("labels", {}).get("job", "") for t in targets]
        assert job_name in job_names, \
            f"'{job_name}' target'ı tanımlı değil. Mevcut: {job_names}"

    @pytest.mark.parametrize("job_name", [
        "cadvisor",
        "mariadb",
        "liderapi",
        "ejabberd",
        "lider-core",
    ])
    def test_prometheus_target_health(self, job_name):
        """Her target'ın scrape durumunu raporla (up/down)."""
        resp = http_get(f"{PROM}/api/v1/targets")
        assert resp and resp.status_code == 200
        targets = resp.json().get("data", {}).get("activeTargets", [])
        target = None
        for t in targets:
            if t.get("labels", {}).get("job") == job_name:
                target = t
                break
        assert target is not None, f"'{job_name}' target'ı bulunamadı"
        health = target.get("health", "unknown")
        last_error = target.get("lastError", "")
        # cadvisor ve mariadb(mysqld-exporter) genellikle çalışır
        # liderapi, ejabberd, lider-core çalışmayabilir — sadece raporla
        if health != "up":
            pytest.fail(
                f"'{job_name}' target durumu: {health}. "
                f"Son hata: {last_error[:200]}. "
                f"Endpoint: {target.get('scrapeUrl', '?')}"
            )

    def test_prometheus_has_metrics(self):
        """Prometheus'ta en az birkaç metrik olmalı."""
        resp = http_get(f"{PROM}/api/v1/query", params={"query": "up"})
        assert resp and resp.status_code == 200
        data = resp.json()
        results = data.get("data", {}).get("result", [])
        assert len(results) > 0, "Prometheus'ta hiç 'up' metriği yok"

    def test_cadvisor_metrics_available(self):
        """cAdvisor container metrikleri Prometheus'ta mevcut olmalı."""
        resp = http_get(f"{PROM}/api/v1/query",
                        params={"query": "container_cpu_usage_seconds_total"})
        assert resp and resp.status_code == 200
        results = resp.json().get("data", {}).get("result", [])
        assert len(results) > 0, "cAdvisor CPU metrikleri bulunamadı"

    def test_cadvisor_memory_metrics(self):
        """cAdvisor bellek metrikleri Prometheus'ta mevcut olmalı."""
        resp = http_get(f"{PROM}/api/v1/query",
                        params={"query": "container_memory_usage_bytes"})
        assert resp and resp.status_code == 200
        results = resp.json().get("data", {}).get("result", [])
        assert len(results) > 0, "cAdvisor bellek metrikleri bulunamadı"


# ─── Grafana Testleri ──────────────────────────────────────────────

class TestGrafana:
    """Grafana'nın çalışma durumu, datasource ve dashboard kontrolü."""

    def test_grafana_health(self):
        """Grafana API sağlıklı olmalı."""
        resp = http_get(f"{GRAFANA}/api/health")
        assert resp and resp.status_code == 200, "Grafana erişilemez"

    def test_grafana_datasources_provisioned(self):
        """Grafana'da en az 1 datasource provisioned olmalı."""
        resp = http_get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
        assert resp and resp.status_code == 200, \
            f"Datasource API: {resp.status_code if resp else 'erişilemez'}"
        datasources = resp.json()
        assert len(datasources) > 0, "Datasource yok"

    def test_grafana_prometheus_datasource(self):
        """Grafana'da Prometheus datasource mevcut olmalı."""
        resp = http_get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
        assert resp and resp.status_code == 200
        datasources = resp.json()
        prom_ds = [ds for ds in datasources if ds.get("type") == "prometheus"]
        assert len(prom_ds) > 0, \
            f"Prometheus datasource bulunamadı. Mevcut: {[ds.get('name') for ds in datasources]}"

    def test_grafana_prometheus_datasource_uid(self):
        """Prometheus datasource UID'si 'prometheus' olmalı (dashboard uyumluluğu)."""
        resp = http_get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
        assert resp and resp.status_code == 200
        datasources = resp.json()
        prom_ds = [ds for ds in datasources if ds.get("type") == "prometheus"]
        if not prom_ds:
            pytest.fail("Prometheus datasource bulunamadı")
        uid = prom_ds[0].get("uid", "")
        assert uid == "prometheus", \
            f"Prometheus datasource UID: '{uid}' (beklenen: 'prometheus'). " \
            f"Dashboard panelleri bu UID'yi referans alır → UID uyuşmazlığı 'No Data' yapar."

    def test_grafana_prometheus_connectivity(self):
        """Grafana → Prometheus bağlantısı çalışmalı."""
        # Datasource'u ID ile bul
        resp = http_get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
        if not resp or resp.status_code != 200:
            pytest.skip("Grafana datasource listesi alınamadı")
        datasources = resp.json()
        prom_ds = [ds for ds in datasources if ds.get("type") == "prometheus"]
        if not prom_ds:
            pytest.fail("Prometheus datasource yok")
        ds_id = prom_ds[0].get("id")
        # Connectivity testi
        resp = http_get(
            f"{GRAFANA}/api/datasources/{ds_id}/health",
            auth=GRAFANA_AUTH
        )
        # Eski Grafana sürümleri /health desteklemeyebilir → proxy query dene
        if resp and resp.status_code == 200:
            return  # Başarılı
        # Fallback: proxy üzerinden query dene
        resp = http_get(
            f"{GRAFANA}/api/datasources/proxy/{ds_id}/api/v1/query",
            params={"query": "up"},
            auth=GRAFANA_AUTH
        )
        if resp and resp.status_code == 200:
            return
        # Son fallback: Prometheus doğrudan erişimi (aynı ağda olup olmadığını test et)
        pytest.fail(
            "Grafana → Prometheus bağlantısı doğrulanamadı. "
            "Ortak ağda (liderahenk_obs) olduklarından emin olun."
        )

    def test_grafana_loki_datasource(self):
        """Grafana'da Loki datasource mevcut olmalı."""
        resp = http_get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
        assert resp and resp.status_code == 200
        datasources = resp.json()
        loki_ds = [ds for ds in datasources if ds.get("type") == "loki"]
        assert len(loki_ds) > 0, "Loki datasource bulunamadı"

    def test_grafana_dashboard_loaded(self):
        """LiderAhenk SLO dashboard yüklenmiş olmalı."""
        resp = http_get(
            f"{GRAFANA}/api/dashboards/uid/liderahenk-slo",
            auth=GRAFANA_AUTH
        )
        assert resp and resp.status_code == 200, \
            f"Dashboard bulunamadı: {resp.status_code if resp else 'erişilemez'}"

    def test_grafana_dashboard_has_panels(self):
        """Dashboard'da en az 4 panel olmalı."""
        resp = http_get(
            f"{GRAFANA}/api/dashboards/uid/liderahenk-slo",
            auth=GRAFANA_AUTH
        )
        if not resp or resp.status_code != 200:
            pytest.fail("Dashboard yüklenemedi")
        dashboard = resp.json().get("dashboard", {})
        panels = dashboard.get("panels", [])
        assert len(panels) >= 4, f"Panel sayısı: {len(panels)}, beklenen >= 4"

    def test_grafana_dashboard_datasource_references(self):
        """Dashboard panellerindeki datasource referansları geçerli olmalı."""
        # Önce mevcut datasource UID'lerini al
        ds_resp = http_get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
        if not ds_resp or ds_resp.status_code != 200:
            pytest.skip("Datasource listesi alınamadı")
        available_uids = {ds.get("uid") for ds in ds_resp.json()}

        # Dashboard panellerini kontrol et
        dash_resp = http_get(
            f"{GRAFANA}/api/dashboards/uid/liderahenk-slo",
            auth=GRAFANA_AUTH
        )
        if not dash_resp or dash_resp.status_code != 200:
            pytest.fail("Dashboard yüklenemedi")
        panels = dash_resp.json().get("dashboard", {}).get("panels", [])
        broken_panels = []
        for panel in panels:
            ds = panel.get("datasource", {})
            ds_uid = ds.get("uid", "") if isinstance(ds, dict) else ""
            if ds_uid and ds_uid not in available_uids:
                broken_panels.append(
                    f"Panel '{panel.get('title', '?')}': uid='{ds_uid}' → BULUNAMADI"
                )
        assert len(broken_panels) == 0, \
            f"Datasource UID uyumsuzluğu (No Data'nın kök nedeni):\n" + \
            "\n".join(broken_panels) + \
            f"\nMevcut UID'ler: {available_uids}"


# ─── Loki Testleri ────────────────────────────────────────────────

class TestLoki:
    """Loki log toplama durumu."""

    def test_loki_ready(self):
        """Loki hazır olmalı."""
        resp = http_get("http://127.0.0.1:3100/ready")
        assert resp and resp.status_code == 200, "Loki erişilemez"

    def test_loki_query_possible(self):
        """Loki'den log sorgusu yapılabilmeli."""
        resp = http_get(
            "http://127.0.0.1:3100/loki/api/v1/labels"
        )
        assert resp is not None, "Loki query API erişilemez"
        assert resp.status_code == 200, f"Loki labels HTTP {resp.status_code}"

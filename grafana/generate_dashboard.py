#!/usr/bin/env python3
"""
Generate Grafana dashboard JSON for Douban iDatabase metrics.
This script reduces boilerplate by using templates and helper functions.
"""

import json
import os
from typing import Dict

# Base dashboard structure
DASHBOARD_BASE = {
    "annotations": {
        "list": [
            {
                "builtIn": 1,
                "datasource": "-- Grafana --",
                "enable": True,
                "hide": True,
                "iconColor": "rgba(0, 211, 255, 1)",
                "name": "Annotations & Alerts",
                "type": "dashboard",
            }
        ]
    },
    "editable": True,
    "gnetId": None,
    "graphTooltip": 0,
    "id": None,
    "links": [],
    "panels": [],
    "refresh": "5s",
    "schemaVersion": 27,
    "style": "dark",
    "tags": [],
    "templating": {"list": []},
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "",
    "title": "Douban iDatabase Dashboard",
    "uid": "douban-idatabase",
    "version": 1,
}


class DashboardGenerator:
    def __init__(self):
        self.dashboard = DASHBOARD_BASE.copy()
        self.panels = []
        self.next_panel_id = 1

    def _get_next_panel_pos(self, h, w):
        """Calculate the next panel position based on height, width"""
        if not self.panels:
            x, y = 0, 0
        elif self.panels[-1]["type"] == "row":
            # If the last panel is a row, start from the next row
            x, y = 0, self.panels[-1]["gridPos"]["y"] + 1
        else:
            last = self.panels[-1]["gridPos"]
            x, y = last["x"] + last["w"], last["y"]
            if x + w > 24:  # Reset to next row
                x = 0
                y += last["h"]
        return {
            "h": h,
            "w": w,
            "x": x,
            "y": y,
        }

    def add_row(self, title: str) -> int:
        """Add a row panel to the dashboard"""
        panel_id = self.next_panel_id
        self.next_panel_id += 1

        row_panel = {
            "collapsed": False,
            "datasource": None,
            "gridPos": self._get_next_panel_pos(1, 24),
            "id": panel_id,
            "title": title,
            "type": "row",
        }

        self.panels.append(row_panel)

    def add_stat_panel(
        self,
        title: str,
        metric: str,
        height: int = 4,
        width: int = 4,
        unit: str = "short",
        color_mode: str = "value",
        threshold_mode: str = "absolute",
    ) -> int:
        """Add a stat panel to the dashboard"""
        panel_id = self.next_panel_id
        self.next_panel_id += 1

        panel = {
            "datasource": None,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "thresholds": {
                        "mode": threshold_mode,
                        "steps": [{"color": "green", "value": None}],
                    },
                    "unit": unit,
                },
                "overrides": [],
            },
            "gridPos": self._get_next_panel_pos(height, width),
            "id": panel_id,
            "options": {
                "colorMode": color_mode,
                "graphMode": "area",
                "justifyMode": "auto",
                "orientation": "auto",
                "reduceOptions": {
                    "calcs": ["lastNotNull"],
                    "fields": "",
                    "values": False,
                },
                "text": {},
                "textMode": "auto",
            },
            "pluginVersion": "7.5.5",
            "targets": [
                {
                    "exemplar": True,
                    "expr": metric,
                    "interval": "",
                    "legendFormat": "",
                    "refId": "A",
                }
            ],
            "title": title,
            "type": "stat",
        }

        self.panels.append(panel)

    def add_graph_panel(
        self,
        title: str,
        metric: str,
        legend_format: str,
        height: int = 8,
        width: int = 12,
        y_axis_label: str = None,
        y_axis_format: str = "short",
    ) -> int:
        """Add a time series graph panel to the dashboard"""
        panel_id = self.next_panel_id
        self.next_panel_id += 1

        panel = {
            "aliasColors": {},
            "bars": False,
            "dashLength": 10,
            "dashes": False,
            "datasource": None,
            "fieldConfig": {"defaults": {}, "overrides": []},
            "fill": 1,
            "fillGradient": 0,
            "gridPos": self._get_next_panel_pos(height, width),
            "hiddenSeries": False,
            "id": panel_id,
            "legend": {
                "avg": False,
                "current": False,
                "max": False,
                "min": False,
                "show": True,
                "total": False,
                "values": False,
            },
            "lines": True,
            "linewidth": 1,
            "nullPointMode": "null",
            "options": {"alertThreshold": True},
            "percentage": False,
            "pluginVersion": "7.5.5",
            "pointradius": 2,
            "points": False,
            "renderer": "flot",
            "seriesOverrides": [],
            "spaceLength": 10,
            "stack": False,
            "steppedLine": False,
            "targets": [
                {
                    "exemplar": True,
                    "expr": metric,
                    "interval": "",
                    "legendFormat": legend_format,
                    "refId": "A",
                }
            ],
            "thresholds": [],
            "timeFrom": None,
            "timeRegions": [],
            "timeShift": None,
            "title": title,
            "tooltip": {"shared": True, "sort": 0, "value_type": "individual"},
            "type": "graph",
            "xaxis": {
                "buckets": None,
                "mode": "time",
                "name": None,
                "show": True,
                "values": [],
            },
            "yaxes": [
                {
                    "format": y_axis_format,
                    "label": y_axis_label,
                    "logBase": 1,
                    "max": None,
                    "min": None,
                    "show": True,
                },
                {
                    "format": "short",
                    "label": None,
                    "logBase": 1,
                    "max": None,
                    "min": None,
                    "show": True,
                },
            ],
            "yaxis": {"align": False, "alignLevel": None},
        }

        self.panels.append(panel)

    def generate_dashboard(self) -> Dict:
        """Generate the complete dashboard"""
        result = self.dashboard.copy()
        result["panels"] = self.panels
        return result


def generate_dashboard():
    """Generate the complete Douban iDatabase dashboard"""
    generator = DashboardGenerator()

    # System & Database Overview
    generator.add_row("System & Database Overview")
    generator.add_stat_panel(
        "Database Size", "douban_idatabase_database_size_bytes", unit="decbytes"
    )
    generator.add_stat_panel(
        "Uptime", "time() - douban_idatabase_process_start_time_seconds", unit="s"
    )

    # Database Metrics
    generator.add_row("Database Metrics")
    generator.add_stat_panel("Fetched Items", "douban_idatabase_fetched_items_total")
    generator.add_stat_panel(
        "Placeholder Items", "douban_idatabase_placeholder_items_total"
    )
    generator.add_stat_panel("Total Items", "douban_idatabase_items_total")

    generator.add_stat_panel("Fetched Lists", "douban_idatabase_fetched_lists_total")
    generator.add_stat_panel(
        "Placeholder Lists", "douban_idatabase_placeholder_lists_total"
    )
    generator.add_stat_panel("Total Lists", "douban_idatabase_lists_total")

    generator.add_stat_panel("Queue Size", "douban_idatabase_queue_size")
    generator.add_stat_panel("History Entries", "douban_idatabase_history_total")

    # API Metrics
    generator.add_row("API Metrics")
    generator.add_graph_panel(
        "API Requests by Endpoint",
        "rate(douban_idatabase_api_requests_total[5m])",
        "{{endpoint}} - {{method}} - {{status}}",
        y_axis_label="requests/sec",
    )
    generator.add_graph_panel(
        "API Response Time (p95)",
        "histogram_quantile(0.95, sum(rate(douban_idatabase_api_request_duration_seconds_bucket[5m])) by (le, endpoint, method))",  # noqa: B950
        "{{endpoint}} - {{method}} (p95)",
        y_axis_format="s",
    )

    # Worker Metrics
    generator.add_row("Worker Metrics")
    generator.add_graph_panel(
        "Worker Processed Items",
        "rate(douban_idatabase_worker_processed_items_total[5m])",
        "{{type}} - {{status}}",
        y_axis_label="items/sec",
    )
    generator.add_graph_panel(
        "Worker Processing Time (p95)",
        "histogram_quantile(0.95, sum(rate(douban_idatabase_worker_processing_duration_seconds_bucket[5m])) by (le, type))",  # noqa: B950
        "{{type}} (p95)",
        y_axis_format="s",
    )

    # Backup Metrics
    generator.add_row("Backup Metrics")
    generator.add_graph_panel(
        "Backup Operations",
        "rate(douban_idatabase_backup_operations_total[1h])",
        "{{status}}",
        y_axis_label="operations/hour",
    )
    generator.add_stat_panel(
        "Backup Duration (p95)",
        "histogram_quantile(0.95, sum(rate(douban_idatabase_backup_duration_seconds_bucket[24h])) by (le))",  # noqa: B950
        unit="s",
    )
    generator.add_stat_panel(
        "Backup File Size",
        "douban_idatabase_backup_file_size_bytes",
        unit="decbytes",
    )

    # Rate Limiting
    generator.add_row("Rate Limiting")
    generator.add_graph_panel(
        "Rate Limit Hits",
        "rate(douban_idatabase_rate_limit_hits_total[5m])",
        "{{host}}",
        width=24,
        y_axis_label="hits/sec",
    )

    # HTTP Metrics
    generator.add_row("HTTP Metrics")
    generator.add_graph_panel(
        "HTTP Requests by Host and Status",
        "rate(douban_idatabase_http_requests_total[5m])",
        "{{host}} - {{status_code}}",
        y_axis_label="requests/sec",
    )
    generator.add_graph_panel(
        "HTTP Response Time by Host (p95)",
        "histogram_quantile(0.95, sum(rate(douban_idatabase_http_request_duration_seconds_bucket[5m])) by (le, host))",  # noqa: B950
        "{{host}} (p95)",
        y_axis_format="s",
    )

    return generator.generate_dashboard()


def main():
    """Generate the dashboard JSON and write to file"""
    dashboard = generate_dashboard()

    # Path to grafana directory
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dashboard.json"
    )

    # Write dashboard JSON to file
    with open(output_path, "w") as f:
        json.dump(dashboard, f, indent=2)

    print(f"Dashboard JSON written to {output_path}")


if __name__ == "__main__":
    main()

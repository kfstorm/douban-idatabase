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

    def add_row(self, title: str) -> None:
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
        show_percentage: bool = True,
        aggregation: str
        | None = "max",  # Added aggregation parameter with default "max"
        legend_format: str = "",  # Added legend format parameter
    ) -> None:
        """Add a stat panel to the dashboard"""
        panel_id = self.next_panel_id
        self.next_panel_id += 1

        # Apply aggregation to the metric
        if aggregation is not None:
            metric = f"{aggregation}({metric})"

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
                "showPercentChange": show_percentage,
            },
            "pluginVersion": "7.5.5",
            "targets": [
                {
                    "exemplar": True,
                    "expr": metric,
                    "interval": "",
                    "legendFormat": legend_format,
                    "refId": "A",
                }
            ],
            "title": title,
            "type": "stat",
        }

        self.panels.append(panel)

    def add_bar_gauge_panel(
        self,
        title: str,
        metric: str,
        height: int = 8,
        width: int = 12,
        orientation: str = "horizontal",
        legend_format: str = "",
        unit: str = "short",
    ) -> None:
        """Add a bar gauge panel to the dashboard"""
        panel_id = self.next_panel_id
        self.next_panel_id += 1

        panel = {
            "datasource": None,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 0,
                        "gradientMode": "none",
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "auto",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"},
                    },
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "green", "value": None}],
                    },
                    "unit": unit,
                },
                "overrides": [],
            },
            "gridPos": self._get_next_panel_pos(height, width),
            "id": panel_id,
            "options": {
                "orientation": orientation,
                "reduceOptions": {
                    "values": False,
                    "calcs": ["lastNotNull"],
                    "fields": "",
                },
                "showUnfilled": True,
            },
            "pluginVersion": "7.5.5",
            "targets": [
                {
                    "exemplar": True,
                    "expr": metric,
                    "interval": "",
                    "legendFormat": legend_format,
                    "refId": "A",
                }
            ],
            "title": title,
            "type": "bargauge",
        }

        self.panels.append(panel)

    def add_graph_panel(
        self,
        title: str,
        metrics: list,
        height: int = 8,
        width: int = 8,
        y_axis_label: str | None = None,
        y_axis_format: str = "short",
    ) -> None:
        """Add a time series graph panel to the dashboard"""
        panel_id = self.next_panel_id
        self.next_panel_id += 1

        targets = []
        # Multiple targets with their own expressions and legend formats
        for idx, target_info in enumerate(metrics):
            targets.append(
                {
                    "exemplar": True,
                    "expr": target_info["expr"],
                    "interval": "",
                    "legendFormat": target_info["legendFormat"],
                    "refId": chr(65 + idx),  # A, B, C, etc.
                }
            )

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
            "targets": targets,
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


# flake8: noqa: E501
def generate_dashboard():
    """Generate the complete Douban iDatabase dashboard"""
    generator = DashboardGenerator()

    # System & Database Overview
    generator.add_row("System & Database Overview")
    generator.add_stat_panel(
        "Database Size",
        "douban_idatabase_database_size_bytes",
        unit="decbytes",
        show_percentage=True,
    )
    generator.add_stat_panel(
        "Uptime",
        "time() - douban_idatabase_process_start_time_seconds",
        unit="s",
        show_percentage=False,
        aggregation="min",
    )

    # Add cumulative panels to overview section
    generator.add_stat_panel(
        "Total Item Operations by Type",
        "sum by (type, operation) (increase(douban_idatabase_item_operations_total[$__range]))",
        height=4,
        width=12,
        unit="short",
        color_mode="value",
        show_percentage=False,
        aggregation=None,
        legend_format="{{type}} - {{operation}}",
    )

    generator.add_stat_panel(
        "Total Change of Items by Type and State",
        "sum by (type, state) (douban_idatabase_items) - sum by (type, state) (douban_idatabase_items offset $__range_s)",
        height=4,
        width=12,
        unit="short",
        color_mode="value",
        show_percentage=False,
        aggregation=None,
        legend_format="{{type}} - {{state}}",
    )

    generator.add_stat_panel(
        "Total Exceptions",
        "sum(increase(douban_idatabase_exceptions_total[$__range]))",
        height=4,
        width=4,
        unit="short",
        color_mode="value",
        show_percentage=False,
        aggregation=None,
    )

    # Database Metrics
    generator.add_row("Database Metrics")

    # Add new panel for tracking item operations
    generator.add_graph_panel(
        "Item Operations by Type",
        [
            {
                "expr": "rate(douban_idatabase_item_operations_total[5m])",
                "legendFormat": "{{type}} - {{operation}}",
            }
        ],
        y_axis_format="recps",
    )

    # Replace item stat panels with graph panel
    generator.add_graph_panel(
        "Items by Type and State",
        [{"expr": "douban_idatabase_items", "legendFormat": "{{type}} - {{state}}"}],
    )

    # Add panel for change rate of items
    generator.add_graph_panel(
        "Change Rate of Items by Type and State (per hour)",
        [
            {
                "expr": "douban_idatabase_items - douban_idatabase_items offset 1h",  # Direct calculation of hourly change
                "legendFormat": "{{type}} - {{state}}",
            }
        ],
        y_axis_label="changes/hour",
    )

    # Replace list stat panels with graph panel
    generator.add_graph_panel(
        "Lists by State",
        [{"expr": "douban_idatabase_lists", "legendFormat": "{{state}}"}],
    )

    # Replace tag stat panels with graph panel
    generator.add_graph_panel(
        "Tags by State",
        [{"expr": "douban_idatabase_tags", "legendFormat": "{{state}}"}],
    )

    # Replace queue size stat panel with graph panel
    generator.add_graph_panel(
        "Queue Size by Type",
        [{"expr": "douban_idatabase_queue_size", "legendFormat": "{{type}}"}],
    )

    generator.add_stat_panel(
        "History Entries", "douban_idatabase_history_total", show_percentage=True
    )

    # API Metrics
    generator.add_row("API Metrics")
    generator.add_graph_panel(
        "API Requests by Endpoint",
        [
            {
                "expr": "rate(douban_idatabase_api_requests_total[5m])",
                "legendFormat": "{{endpoint}} - {{method}} - {{status}}",
            }
        ],
        y_axis_format="reqps",
    )
    generator.add_graph_panel(
        "API Response Time (avg and p95)",
        [
            {
                "expr": "histogram_quantile(0.95, sum(rate(douban_idatabase_api_request_duration_seconds_bucket[5m])) by (le, endpoint, method))",
                "legendFormat": "{{endpoint}} - {{method}} (p95)",
            },
            {
                "expr": "avg(rate(douban_idatabase_api_request_duration_seconds_sum[5m]) / rate(douban_idatabase_api_request_duration_seconds_count[5m])) by (endpoint, method)",
                "legendFormat": "{{endpoint}} - {{method}} (avg)",
            },
        ],
        y_axis_format="s",
    )

    # User Metrics
    generator.add_row("User Metrics")

    # Total API Requests by User (Bar Gauge)
    generator.add_bar_gauge_panel(
        "Total API Requests by User",
        "sum by (user_id) (increase(douban_idatabase_user_requests_total[$__range]))",
        height=8,
        width=12,
        orientation="horizontal",
        legend_format="User {{user_id}}",
        unit="short",
    )

    # User API Requests
    generator.add_graph_panel(
        "API Requests by User",
        [
            {
                "expr": "sum(rate(douban_idatabase_user_requests_total[5m])) by (user_id)",
                "legendFormat": "User {{user_id}}",
            }
        ],
        y_axis_format="reqps",
    )

    # Top Users by API Requests
    generator.add_graph_panel(
        "Top 5 Users by API Requests",
        [
            {
                "expr": "topk(5, sum(rate(douban_idatabase_user_requests_total[5m])) by (user_id))",
                "legendFormat": "User {{user_id}}",
            }
        ],
        y_axis_format="reqps",
    )

    # Rate Limit Usage
    generator.add_graph_panel(
        "Rate Limit Current Usage by User",
        [
            {
                "expr": "douban_idatabase_user_rate_limit_current",
                "legendFormat": "User {{user_id}}",
            }
        ],
    )

    # Rate Limit Hits
    generator.add_graph_panel(
        "Rate Limit Hits",
        [
            {
                "expr": "rate(douban_idatabase_user_rate_limit_hits_total[5m])",
                "legendFormat": "User {{user_id}}",
            }
        ],
        y_axis_format="rpm",
    )

    # Rate Limit Heat Map
    generator.add_stat_panel(
        "Total Rate Limit Hits (1h)",
        "sum(increase(douban_idatabase_user_rate_limit_hits_total[1h]))",
        color_mode="value",
        threshold_mode="absolute",
        aggregation=None,
    )

    # Worker Metrics
    generator.add_row("Worker Metrics")
    generator.add_graph_panel(
        "Worker Processed Items",
        [
            {
                "expr": "rate(douban_idatabase_worker_processed_items_total[5m])",
                "legendFormat": "{{type}} - {{status}}",
            }
        ],
        y_axis_format="recps",
    )
    generator.add_graph_panel(
        "Worker Processing Time (avg and p95)",
        [
            {
                "expr": "histogram_quantile(0.95, sum(rate(douban_idatabase_worker_processing_duration_seconds_bucket[5m])) by (le, type))",
                "legendFormat": "{{type}} (p95)",
            },
            {
                "expr": "avg(rate(douban_idatabase_worker_processing_duration_seconds_sum[5m]) / rate(douban_idatabase_worker_processing_duration_seconds_count[5m])) by (type)",
                "legendFormat": "{{type}} (avg)",
            },
        ],
        y_axis_format="s",
    )

    # Backup Metrics
    generator.add_row("Backup Metrics")
    generator.add_graph_panel(
        "Backup Operations",
        [
            {
                "expr": "rate(douban_idatabase_backup_operations_total[1h])",
                "legendFormat": "{{status}}",
            }
        ],
        y_axis_label="operations/hour",
    )
    generator.add_stat_panel(
        "Backup Duration (p95)",
        "histogram_quantile(0.95, sum(rate(douban_idatabase_backup_duration_seconds_bucket[24h])) by (le))",
        unit="s",
        show_percentage=True,
        aggregation=None,  # No additional aggregation needed
    )
    generator.add_stat_panel(
        "Backup File Size",
        "douban_idatabase_backup_file_size_bytes",
        unit="decbytes",
        show_percentage=True,
    )

    # HTTP Metrics
    generator.add_row("HTTP Metrics")
    generator.add_graph_panel(
        "HTTP Requests by Host, Status, and Strategy",
        [
            {
                "expr": "rate(douban_idatabase_http_requests_total[5m])",
                "legendFormat": "{{host}} - {{status_code}} - {{strategy}}",
            }
        ],
        y_axis_format="reqps",
    )
    generator.add_graph_panel(
        "HTTP Response Time by Host (avg and p95)",
        [
            {
                "expr": "histogram_quantile(0.95, sum(rate(douban_idatabase_http_request_duration_seconds_bucket[5m])) by (le, host))",
                "legendFormat": "{{host}} (p95)",
            },
            {
                "expr": "avg(rate(douban_idatabase_http_request_duration_seconds_sum[5m]) / rate(douban_idatabase_http_request_duration_seconds_count[5m])) by (host)",
                "legendFormat": "{{host}} (avg)",
            },
        ],
        y_axis_format="s",
    )

    # Exceptions
    generator.add_row("Exceptions")

    generator.add_graph_panel(
        "Exception Rate by Type and Module",
        [
            {
                "expr": "rate(douban_idatabase_exceptions_total[5m])",
                "legendFormat": "{{type}} - {{module}}",
            }
        ],
        y_axis_format="ops",
        y_axis_label="exceptions/sec",
    )
    generator.add_stat_panel(
        "Total Exceptions (1h)",
        "sum(increase(douban_idatabase_exceptions_total[1h]))",
        color_mode="value",
        threshold_mode="absolute",
        unit="short",
        aggregation=None,  # No additional aggregation needed - already using sum
    )
    generator.add_stat_panel(
        "Total Exceptions (24h)",
        "sum(increase(douban_idatabase_exceptions_total[24h]))",
        color_mode="value",
        threshold_mode="absolute",
        unit="short",
        aggregation=None,  # No additional aggregation needed - already using sum
    )

    # Proxy Metrics
    generator.add_row("Proxy Metrics")
    generator.add_graph_panel(
        "Proxy Failures by Proxy ID",
        [
            {
                "expr": "rate(douban_idatabase_proxy_failures_total[5m])",
                "legendFormat": "{{proxy_id}}",
            }
        ],
        y_axis_format="ops",
        y_axis_label="failures/sec",
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

#!/usr/bin/env python
""" cdk8s app for monitoring services with Grafana Agent. """
import ruamel.yaml
import yaml as pyyaml
from cdk8s import App, Chart, Helm, Include
from constructs import Construct
from jinja2 import Environment, FileSystemLoader

from imports import k8s

with open("config.yaml", "r") as file:
    config = pyyaml.safe_load(file)


class MonitoringNamespace(Chart):
    """Create namespace for monitoring services like Grafana Agent."""

    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)

        k8s.KubeNamespace(
            self, "monitoring", metadata=k8s.ObjectMeta(name="monitoring")
        )


class GrafanaAgent(Chart):
    """Install and configure Grafana Agent for both metrics and logging."""

    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id, namespace="monitoring")

        Helm(
            self,
            "kube-state-metrics",
            chart="prometheus-community/kube-state-metrics",
            values={"image": {"tag": "v2.4.2"}},
            helm_flags=["--namespace=monitoring"],
        )

        Include(self, "agent-metrics", url="configs/agent-bare.yaml")

        jinja = Environment(
            loader=FileSystemLoader("."), trim_blocks=True, lstrip_blocks=True
        )
        yaml = ruamel.yaml.YAML(typ=["rt", "string"])
        yaml.allow_duplicate_keys = True
        yaml.explicit_start = True
        metrics_template = jinja.get_template("templates/metrics-configmap.yaml")
        yaml_content = yaml.load(
            metrics_template.render(
                metrics_url=config["metrics"]["url"],
                metrics_username=config["metrics"]["username"],
                metrics_password=config["metrics"]["password"],
                logs_url=config["logs"]["url"],
                logs_username=config["logs"]["username"],
                logs_password=config["logs"]["password"],
            )
        )
        with open("configs/metrics-configmap.yaml", "w") as the_file:
            the_file.write(yaml.dump_to_string(yaml_content))

        Include(self, "metrics-configuration", url="configs/metrics-configmap.yaml")

        logs_template = jinja.get_template("templates/logs-configmap.yaml")
        logs_content = yaml.load(
            logs_template.render(
                metrics_url=config["metrics"]["url"],
                metrics_username=config["metrics"]["username"],
                metrics_password=config["metrics"]["password"],
                logs_url=config["logs"]["url"],
                logs_username=config["logs"]["username"],
                logs_password=config["logs"]["password"],
            )
        )
        with open("configs/logs-configmap.yaml", "w") as the_file:
            the_file.write(yaml.dump_to_string(logs_content))

        Include(self, "logs-configuration", url="configs/logs-configmap.yaml")


app = App()

monitoring_ns = MonitoringNamespace(app, "monitoring-namespace")
grafana_agent = GrafanaAgent(app, "grafana-agent")
grafana_agent.add_dependency(monitoring_ns)

app.synth()

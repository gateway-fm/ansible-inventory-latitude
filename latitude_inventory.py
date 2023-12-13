from contextlib import suppress
from typing import TypedDict

import requests
from ansible.inventory.data import InventoryData
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

DOCUMENTATION = r"""
    name: latitude_inventory
    plugin_type: inventory
    short_description: Latitude inventory source
    extends_documentation_fragment:
        - inventory_cache
        - constructed
    description:
        - Get inventory hosts from Latitude cloud.
        - Uses a YAML configuration file that ends with C(latitude.{yml|yaml}).
    author:
        - Vladislav Polskikh
    options:
        plugin:
            description: Token that ensures this is a source file for the plugin
            required: true
            choices: ['latitude_inventory']
        latitude_project:
            description: >
                Latitude L(projects,https://docs.latitude.sh/reference/get-servers)
            type: string
            required: True
        latitude_api_token:
            description: Latitude API token
            type: string
            env:
                - name: LATITUDE_API_TOKEN
        include_tags:
            type: list
            elements: string
            description: >
                If specified, only hosts tagged with specific tags will be added to the inventory.
        exclude_tags:
            type: list
            elements: string
            description: >
                If specified, hosts tagged with specific tags will be excluded from the inventory.

"""


class Features(TypedDict):
    raid: bool
    rescue: bool
    ssh_keys: bool
    user_data: bool


class Distro(TypedDict):
    name: str
    series: str
    slug: str


class OperatingSystem(TypedDict):
    name: str
    slug: str
    version: str
    distro: Distro
    features: Features


class Plan(TypedDict):
    id: str
    name: str
    billing: str
    slug: str


class Region(TypedDict):
    city: str
    country: str
    site: dict


class ServerAttributes(TypedDict):
    created_at: str
    hostname: str
    ipmi_status: str
    label: str
    operating_system: OperatingSystem
    plan: Plan
    price: int
    primary_ipv4: str
    project: dict
    region: Region
    role: str
    specs: dict
    status: str
    team: dict


class Server(TypedDict):
    id: str
    type: str
    attributes: ServerAttributes


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "latitude_inventory"

    def verify_file(self, path: str):
        """return true/false if this is possibly a valid file for this plugin to consume"""
        return super(InventoryModule, self).verify_file(path) and path.endswith(
            ("latitude.yaml", "latitude.yml")
        )

    def parse(
        self,
        inventory: InventoryData,
        loader: DataLoader,
        path: str,
        cache: bool = True,
    ):
        # call base method to ensure properties are available for use with other helper methods
        super().parse(inventory, loader, path, cache)
        # this method will parse 'common format' inventory sources and
        # update any options declared in DOCUMENTATION as needed
        self._read_config_data(path)
        servers = self.get_servers()

        for server in servers:
            self.add_sever(Server(server))

    def get_servers(self) -> list[Server]:
        latitude_project = self.get_option("latitude_project")
        latitude_api_token = self.get_option("latitude_api_token")
        url = "https://api.latitude.sh/servers"
        headers = {
            "accept": "application/json",
            "Authorization": latitude_api_token,
        }
        # I didn't find how to disable pagination in their API.
        # And it wasn't clear from the endpoint documentation that by default it returns 20 servers.
        # Another solution would be to hardcode ?page[size]= to something really big, but we don't know
        # It could affect performance or API will return an error if we request e.g. 1000 servers. It could be very slow or die.
        # https://docs.latitude.sh/reference/pagination
        page = 1
        all_servers = []
        while True:
            params = {
                "filter[project]": latitude_project,
                "sort": "id",
                "page[number]": page,
            }
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            servers = response.json().get("data", [])
            if not servers:
                break
            all_servers += servers
            page += 1
        return all_servers

    def add_sever(self, server: Server) -> None:
        server_attributes = server["attributes"]
        hostname = server_attributes["hostname"]
        group = self.get_hosts_group(hostname)

        self.inventory.add_host(hostname, group=group)

        host_vars = {}
        host_vars["public_ip_address"] = server_attributes["primary_ipv4"]
        host_vars["server_name"] = hostname
        host_vars["group"] = group
        for var_name, var_value in host_vars.items():
            self.inventory.set_variable(hostname, var_name, var_value)

        # Determines if composed variables or groups using nonexistent variables is an error
        strict = self.get_option("strict")

        # Add variables created by the user's Jinja2 expressions to the host
        self._set_composite_vars(
            self.get_option("compose"), host_vars, hostname, strict=True
        )

        # The following two methods combine the provided variables dictionary with the latest host variables
        # Using these methods after _set_composite_vars() allows groups to be created with the composed variables
        self._add_host_to_composed_groups(
            self.get_option("groups"), host_vars, hostname, strict=strict
        )
        self._add_host_to_keyed_groups(
            self.get_option("keyed_groups"), host_vars, hostname, strict=strict
        )

    def get_hosts_group(self, hostname: str) -> str | None:
        group = None
        with suppress(IndexError):
            group = hostname.split("-")[1]
            self.inventory.add_group(group)
        include_tags = self.get_option("include_tags")
        if include_tags and include_tags != group:
            return None
        exclude_tags = self.get_option("exclude_tags")
        if exclude_tags and exclude_tags == group:
            return None
        return group

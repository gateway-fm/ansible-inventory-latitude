## Dynamic Ansible inventory plugin for Latitude
---
## Installation notes

* Clone the repository

* Set environment variables so that Ansible will recognize the plugin
  * ```export ANSIBLE_INVENTORY_PLUGINS=/full/path/to/ansible-inventory-latitude/```
  * ```export ANSIBLE_LIBRARY=/full/path/to/ansible-inventory-latitude```
  * ```export ANSIBLE_INVENTORY_ENABLED=latitude_inventory```

Credentials are provided by LATITUDE_API_TOKEN environment variable.
This can be overridden by explicitly specifying latitude_api_token in an inventory file.

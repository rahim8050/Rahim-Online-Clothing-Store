# Template tags

`has_group` filter checks if the current user belongs to a given Django group.

```django
{% load roles %}
{% if user|has_group:"Vendor" %}
  <!-- content for vendor -->
{% endif %}
```

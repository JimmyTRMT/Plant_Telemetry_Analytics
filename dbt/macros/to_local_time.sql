{#- Convert a naive UTC timestamp to the naive local time of an IANA timezone. -#}
{% macro to_local_time(utc_timestamp, timezone_name) -%}
    timezone({{ timezone_name }}, {{ utc_timestamp }} at time zone 'UTC')
{%- endmacro %}

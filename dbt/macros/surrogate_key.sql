{% macro surrogate_key(columns) -%}
    md5(concat_ws('||'
        {%- for column in columns -%}
        , coalesce(cast({{ column }} as varchar), '')
        {%- endfor -%}
    ))
{%- endmacro %}

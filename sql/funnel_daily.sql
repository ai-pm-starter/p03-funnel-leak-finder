-- Funnel Leak Finder (P3-03): sessions per day x segment, and how far each session got in the funnel.
-- Source: Google Merchandise Store GA4 sample (public, obfuscated). Scans about 1 GB.
-- A session "reached" a step if it fired that event or any later one, so the funnel only ever narrows
-- and purchases are never lost when GA4 skipped an earlier event in the same session.
with events as (
  select
    user_pseudo_id,
    (select value.int_value from unnest(event_params) where key = 'ga_session_id')     as session_id,
    (select value.int_value from unnest(event_params) where key = 'ga_session_number') as session_number,
    parse_date('%Y%m%d', event_date) as day,
    device.category       as device,
    geo.country           as country,
    traffic_source.medium as medium,
    case event_name
      when 'session_start'     then 1
      when 'view_item'         then 2
      when 'add_to_cart'       then 3
      when 'begin_checkout'    then 4
      when 'add_shipping_info' then 5
      when 'add_payment_info'  then 6
      when 'purchase'          then 7
      else 1 end as step,
    if(event_name = 'purchase', ecommerce.purchase_revenue_in_usd, 0) as revenue
  from `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
sessions as (
  select
    user_pseudo_id, session_id,
    min(day)                    as day,
    any_value(device)           as device,
    any_value(country)          as country,
    any_value(medium)           as medium,
    min(session_number)         as session_number,
    max(step)                   as deepest_step,
    countif(step = 7)           as purchases,
    sum(revenue)                as revenue
  from events
  where session_id is not null
  group by 1, 2
)
select
  day,
  device,
  country,
  case
    when medium = 'organic'  then 'organic'
    when medium = '(none)'   then 'direct'
    when medium = 'referral' then 'referral'
    when medium = 'cpc'      then 'paid'
    when medium in ('<Other>', '(data deleted)') or medium is null then 'unknown'
    else 'other' end                                          as channel,
  if(session_number = 1, 'new', 'returning')                  as visitor,
  count(*)                                                    as sessions,
  countif(deepest_step >= 2) as view_item,
  countif(deepest_step >= 3) as add_to_cart,
  countif(deepest_step >= 4) as begin_checkout,
  countif(deepest_step >= 5) as add_shipping_info,
  countif(deepest_step >= 6) as add_payment_info,
  countif(deepest_step >= 7) as purchase,
  sum(purchases)                                              as purchase_events,
  round(sum(revenue), 2)                                      as revenue_usd
from sessions
group by 1, 2, 3, 4, 5
order by 1, 2, 3, 4, 5

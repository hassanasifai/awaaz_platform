=== Awaaz — COD Confirmation Agent ===
Contributors: gelecek
Tags: woocommerce, cod, urdu, whatsapp, ai
Requires at least: 6.0
Tested up to: 6.7
Requires PHP: 8.1
WC requires at least: 9.0
WC tested up to: 9.4
Stable tag: 0.1.0
License: Proprietary

Connects your WooCommerce store to Awaaz, a conversational Urdu AI agent that confirms COD orders over WhatsApp.

== Description ==

Awaaz is a multi-tenant WhatsApp-first conversational AI platform built for Pakistani e-commerce. This plugin registers your WooCommerce store with Awaaz and forwards COD orders for confirmation; outcomes (confirmed/cancelled/rescheduled/change-request/escalated) flow back as order status changes and meta fields.

== Installation ==

1. Install and activate the plugin.
2. Go to **WooCommerce → Awaaz** and paste your API base URL, merchant ID, and signing secret from the Awaaz dashboard.
3. Place a test COD order; you should see the order arrive in the Awaaz dashboard within seconds.

== Privacy ==

The plugin sends order details (customer name, phone, address, items, total) to your configured Awaaz instance. No data is sent until you configure an API key.

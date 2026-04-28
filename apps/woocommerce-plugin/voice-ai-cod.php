<?php
/**
 * Plugin Name: Awaaz — COD Confirmation Agent
 * Plugin URI: https://awaaz.pk/woocommerce
 * Description: Connects your WooCommerce store to Awaaz, a conversational Urdu AI agent that confirms COD orders over WhatsApp.
 * Version: 0.1.0
 * Requires at least: 6.0
 * Requires PHP: 8.1
 * Author: Gelecek Solution
 * Author URI: https://gelecek.solutions
 * License: Proprietary
 * Text Domain: awaaz
 * Domain Path: /languages
 * WC requires at least: 9.0
 * WC tested up to: 9.4
 */

defined( 'ABSPATH' ) || exit;

define( 'AWAAZ_VERSION', '0.1.0' );
define( 'AWAAZ_PLUGIN_FILE', __FILE__ );
define( 'AWAAZ_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );

require_once AWAAZ_PLUGIN_DIR . 'includes/class-vai-plugin.php';
require_once AWAAZ_PLUGIN_DIR . 'includes/class-vai-api.php';
require_once AWAAZ_PLUGIN_DIR . 'includes/class-vai-webhook.php';
require_once AWAAZ_PLUGIN_DIR . 'includes/class-vai-settings.php';
require_once AWAAZ_PLUGIN_DIR . 'includes/class-vai-order-meta.php';

add_action( 'plugins_loaded', array( 'Awaaz\\VAI_Plugin', 'instance' ) );

register_activation_hook( __FILE__, array( 'Awaaz\\VAI_Plugin', 'activate' ) );
register_deactivation_hook( __FILE__, array( 'Awaaz\\VAI_Plugin', 'deactivate' ) );

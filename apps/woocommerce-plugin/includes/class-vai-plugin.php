<?php
namespace Awaaz;

defined( 'ABSPATH' ) || exit;

/**
 * Plugin lifecycle + hook registration.
 */
class VAI_Plugin {

    /** @var self|null */
    private static $instance = null;

    /** @return self */
    public static function instance() {
        if ( null === self::$instance ) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        if ( ! class_exists( 'WooCommerce' ) ) {
            add_action( 'admin_notices', array( $this, 'woo_missing_notice' ) );
            return;
        }

        // Order events
        add_action( 'woocommerce_new_order', array( '\\Awaaz\\VAI_API', 'on_new_order' ), 20, 1 );
        add_action(
            'woocommerce_order_status_changed',
            array( '\\Awaaz\\VAI_API', 'on_status_changed' ),
            20,
            4
        );

        // Inbound webhook (outcomes from Awaaz)
        add_action( 'rest_api_init', array( '\\Awaaz\\VAI_Webhook', 'register_routes' ) );

        // Settings page
        add_action( 'admin_menu', array( '\\Awaaz\\VAI_Settings', 'add_menu' ) );
        add_action( 'admin_init', array( '\\Awaaz\\VAI_Settings', 'register' ) );

        // Order meta column
        add_filter(
            'manage_edit-shop_order_columns',
            array( '\\Awaaz\\VAI_Order_Meta', 'add_column' )
        );
        add_action(
            'manage_shop_order_posts_custom_column',
            array( '\\Awaaz\\VAI_Order_Meta', 'render_column' ),
            10,
            2
        );
    }

    public static function activate() {
        if ( false === get_option( 'awaaz_options' ) ) {
            add_option(
                'awaaz_options',
                array(
                    'api_key'        => '',
                    'api_base_url'   => 'https://api.awaaz.pk',
                    'merchant_id'    => '',
                    'enable_dispatch' => true,
                )
            );
        }
    }

    public static function deactivate() {}

    public function woo_missing_notice() {
        echo '<div class="notice notice-error"><p><strong>Awaaz</strong> requires WooCommerce to be installed and active.</p></div>';
    }
}

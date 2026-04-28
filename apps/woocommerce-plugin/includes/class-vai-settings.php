<?php
namespace Awaaz;

defined( 'ABSPATH' ) || exit;

class VAI_Settings {

    public static function add_menu() {
        add_submenu_page(
            'woocommerce',
            __( 'Awaaz', 'awaaz' ),
            __( 'Awaaz', 'awaaz' ),
            'manage_woocommerce',
            'awaaz-settings',
            array( __CLASS__, 'render' )
        );
    }

    public static function register() {
        register_setting(
            'awaaz',
            'awaaz_options',
            array( 'sanitize_callback' => array( __CLASS__, 'sanitize' ) )
        );
        add_settings_section( 'awaaz_main', __( 'Connection', 'awaaz' ), '__return_false', 'awaaz' );
        self::add_field( 'api_base_url', __( 'API base URL', 'awaaz' ) );
        self::add_field( 'merchant_id', __( 'Merchant ID', 'awaaz' ) );
        self::add_field( 'api_key', __( 'API key (signing secret)', 'awaaz' ), true );
        self::add_field( 'enable_dispatch', __( 'Enable dispatch', 'awaaz' ), false, 'checkbox' );
    }

    public static function sanitize( $input ) {
        return array(
            'api_base_url'    => esc_url_raw( $input['api_base_url'] ?? '' ),
            'merchant_id'     => sanitize_text_field( $input['merchant_id'] ?? '' ),
            'api_key'         => sanitize_text_field( $input['api_key'] ?? '' ),
            'enable_dispatch' => ! empty( $input['enable_dispatch'] ),
        );
    }

    private static function add_field( $key, $label, $is_secret = false, $type = 'text' ) {
        add_settings_field(
            $key,
            $label,
            function () use ( $key, $is_secret, $type ) {
                $opts = get_option( 'awaaz_options' );
                $val  = $opts[ $key ] ?? '';
                if ( 'checkbox' === $type ) {
                    printf(
                        '<input type="checkbox" name="awaaz_options[%s]" value="1" %s />',
                        esc_attr( $key ),
                        checked( $val, true, false )
                    );
                    return;
                }
                printf(
                    '<input type="%s" name="awaaz_options[%s]" value="%s" class="regular-text" />',
                    $is_secret ? 'password' : 'text',
                    esc_attr( $key ),
                    esc_attr( $val )
                );
            },
            'awaaz',
            'awaaz_main'
        );
    }

    public static function render() {
        echo '<div class="wrap"><h1>Awaaz</h1><form method="post" action="options.php">';
        settings_fields( 'awaaz' );
        do_settings_sections( 'awaaz' );
        submit_button();
        echo '</form></div>';
    }
}

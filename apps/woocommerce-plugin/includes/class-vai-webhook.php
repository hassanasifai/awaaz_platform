<?php
namespace Awaaz;

defined( 'ABSPATH' ) || exit;

/**
 * Inbound webhook from Awaaz — outcome events update WC order status + meta.
 */
class VAI_Webhook {

    public static function register_routes() {
        register_rest_route(
            'awaaz/v1',
            '/outcome',
            array(
                'methods'             => 'POST',
                'callback'            => array( __CLASS__, 'handle' ),
                'permission_callback' => array( __CLASS__, 'verify' ),
            )
        );
    }

    public static function verify( $request ) {
        $opts      = get_option( 'awaaz_options' );
        $secret    = $opts['api_key'] ?? '';
        $signature = $request->get_header( 'x_awaaz_signature' );
        if ( empty( $signature ) || empty( $secret ) ) {
            return false;
        }
        $expected = 'sha256=' . hash_hmac( 'sha256', $request->get_body(), $secret );
        return hash_equals( $expected, $signature );
    }

    public static function handle( $request ) {
        $body = json_decode( $request->get_body(), true );
        if ( ! is_array( $body ) || empty( $body['order_id'] ) ) {
            return new \WP_REST_Response( array( 'error' => 'invalid' ), 400 );
        }
        $order = wc_get_order( $body['order_id'] );
        if ( ! $order ) {
            return new \WP_REST_Response( array( 'error' => 'not found' ), 404 );
        }

        $outcome = $body['outcome'] ?? '';
        $reason  = $body['reason'] ?? '';
        $order->update_meta_data( '_awaaz_outcome', $outcome );
        if ( $reason ) {
            $order->update_meta_data( '_awaaz_outcome_reason', $reason );
        }

        switch ( $outcome ) {
            case 'confirmed':
                $order->update_status( 'processing', __( 'Awaaz: customer confirmed COD.', 'awaaz' ) );
                break;
            case 'cancelled':
                $order->update_status(
                    'cancelled',
                    sprintf( __( 'Awaaz: customer cancelled COD (%s).', 'awaaz' ), $reason )
                );
                break;
            case 'rescheduled':
                $order->update_status( 'on-hold', __( 'Awaaz: rescheduled by customer.', 'awaaz' ) );
                break;
            case 'change_request':
            case 'escalated':
                $order->update_status( 'on-hold', __( 'Awaaz: needs operator review.', 'awaaz' ) );
                break;
        }

        $order->save();
        return new \WP_REST_Response( array( 'status' => 'ok' ), 200 );
    }
}

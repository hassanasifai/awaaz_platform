<?php
namespace Awaaz;

defined( 'ABSPATH' ) || exit;

/**
 * Outbound API client to the Awaaz control plane.
 */
class VAI_API {

    /**
     * @param int $order_id
     */
    public static function on_new_order( $order_id ) {
        $order = wc_get_order( $order_id );
        if ( ! $order || $order->get_payment_method() !== 'cod' ) {
            return;
        }
        self::dispatch( $order, 'new' );
    }

    /**
     * @param int      $order_id
     * @param string   $old_status
     * @param string   $new_status
     * @param \WC_Order $order
     */
    public static function on_status_changed( $order_id, $old_status, $new_status, $order ) {
        if ( $order->get_payment_method() !== 'cod' ) {
            return;
        }
        // Only re-dispatch when transitioning out of pending/on-hold to processing.
        if ( in_array( $old_status, array( 'pending', 'on-hold' ), true ) && $new_status === 'processing' ) {
            self::dispatch( $order, 'status_changed' );
        }
    }

    private static function dispatch( $order, $event ) {
        $opts = get_option( 'awaaz_options' );
        if ( empty( $opts['api_key'] ) || empty( $opts['merchant_id'] ) ) {
            return;
        }
        if ( empty( $opts['enable_dispatch'] ) ) {
            return;
        }

        $payload = self::serialize_order( $order );
        $body    = wp_json_encode( $payload );
        $sig     = 'sha256=' . hash_hmac( 'sha256', $body, $opts['api_key'] );

        $url = trailingslashit( $opts['api_base_url'] ) . 'v1/orders/intake';

        wp_remote_post(
            $url,
            array(
                'timeout' => 8,
                'headers' => array(
                    'Content-Type'      => 'application/json',
                    'X-Awaaz-Signature' => $sig,
                    'X-Awaaz-Source'    => 'woocommerce/' . $event,
                ),
                'body'    => $body,
            )
        );
    }

    private static function serialize_order( $order ) {
        $items = array();
        foreach ( $order->get_items() as $item ) {
            $items[] = array(
                'name'       => $item->get_name(),
                'qty'        => (int) $item->get_quantity(),
                'unit_price' => (float) $order->get_item_total( $item, false, false ),
            );
        }
        $opts = get_option( 'awaaz_options' );

        return array(
            'merchant_id'      => $opts['merchant_id'],
            'platform'         => 'woocommerce',
            'order_id'         => (string) $order->get_id(),
            'external_order_id' => $order->get_order_number(),
            'customer'         => array(
                'name'     => trim( $order->get_billing_first_name() . ' ' . $order->get_billing_last_name() ),
                'phone'    => $order->get_billing_phone(),
                'language' => 'ur',
            ),
            'address'          => array(
                'line1'       => $order->get_shipping_address_1() ?: $order->get_billing_address_1(),
                'line2'       => $order->get_shipping_address_2() ?: $order->get_billing_address_2(),
                'city'        => $order->get_shipping_city() ?: $order->get_billing_city(),
                'province'    => $order->get_shipping_state() ?: $order->get_billing_state(),
                'postal_code' => $order->get_shipping_postcode() ?: $order->get_billing_postcode(),
            ),
            'items'            => $items,
            'subtotal'         => (float) $order->get_subtotal(),
            'shipping'         => (float) $order->get_shipping_total(),
            'total'            => (float) $order->get_total(),
            'cod_amount'       => (float) $order->get_total(),
            'currency'         => $order->get_currency(),
            'placed_at'        => gmdate( 'c', $order->get_date_created()->getTimestamp() ),
            'idempotency_key'  => 'woo-' . $order->get_id() . '-' . $order->get_date_modified()->getTimestamp(),
        );
    }
}

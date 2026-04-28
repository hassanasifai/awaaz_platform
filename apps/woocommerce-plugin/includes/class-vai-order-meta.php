<?php
namespace Awaaz;

defined( 'ABSPATH' ) || exit;

class VAI_Order_Meta {

    public static function add_column( $columns ) {
        $new = array();
        foreach ( $columns as $key => $label ) {
            $new[ $key ] = $label;
            if ( 'order_status' === $key ) {
                $new['awaaz_outcome'] = __( 'Awaaz', 'awaaz' );
            }
        }
        return $new;
    }

    public static function render_column( $column, $post_id ) {
        if ( 'awaaz_outcome' !== $column ) {
            return;
        }
        $outcome = get_post_meta( $post_id, '_awaaz_outcome', true );
        if ( ! $outcome ) {
            echo '—';
            return;
        }
        $colors = array(
            'confirmed'      => '#16a34a',
            'cancelled'      => '#ef4444',
            'rescheduled'    => '#0ea5e9',
            'change_request' => '#f59e0b',
            'escalated'      => '#a855f7',
        );
        $color = $colors[ $outcome ] ?? '#64748b';
        printf(
            '<span style="background:%s;color:white;padding:2px 8px;border-radius:9999px;font-size:11px">%s</span>',
            esc_attr( $color ),
            esc_html( $outcome )
        );
    }
}

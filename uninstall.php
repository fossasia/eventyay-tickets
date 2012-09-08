<?php
/*
	The uninstall file
	(to make your blog always clean when you need to test plugins :p)
*/

if( !defined( 'ABSPATH') &&  !defined('WP_UNINSTALL_PLUGIN') )
	    exit();
	
	global $wpdb;
	
	// delete widget option
	delete_option( 'widget_juiz_last_tweet_widget');
	// delete plugin feeds cache (options)
	$wpdb->query( 'DELETE FROM ' . $wpdb->options . ' WHERE option_name LIKE "juiz_ltw_%"' );


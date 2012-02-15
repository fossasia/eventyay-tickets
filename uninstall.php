<?php
/*
	The uninstall file
	(to make your blog always clean when you need to test plugins :p)
*/

global $wpdb;

if( !defined( 'ABSPATH') &&  !defined('WP_UNINSTALL_PLUGIN') )
	    exit();
	
	delete_option( 'widget_juiz_last_tweet_widget');


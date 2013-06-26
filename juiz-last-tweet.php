<?php
/**
 * Plugin Name: Juiz Last Tweet Widget
 * Plugin URI: http://www.creativejuiz.fr/blog/wordpress/wordpress-plugin-afficher-derniers-tweets-widget
 * Description: Adds a widget to your blog's sidebar to show your latest tweets. (XHTML-valid - No JS used to load tweets) - <a href="https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=P39NJPCWVXGDY&lc=FR&item_name=Juiz%20Last%20Tweet%20Widget%20%2d%20WordPress%20Plugin&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHostedGuest" title="Thank you!">Donate to contribute</a>
 * Author: Geoffrey Crofte
 * Version: 1.2.2
 * Author URI: http://crofte.fr
 * License: GPLv2 or later 
 */
/* 
	Changelog => See readme.txt
*/
/**
Copyright 2011 -  Geoffrey Crofte  (email : support@creativejuiz.com)

    
This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
**/

define( 'JUIZ_LTW_PLUGIN_NAME',	 	'Juiz Last Tweet Widget' );
define( 'JUIZ_LTW_VERSION', 		'1.2.2' );
define( 'JUIZ_LTW_FILE',		 	__FILE__ );
define( 'JUIZ_LTW_DIRNAME', 		basename( dirname( __FILE__ ) ) );
define( 'JUIZ_LTW_PLUGIN_URL',	 	plugin_dir_url( __FILE__ ));
define( 'JUIZ_LTW_SLUG',		 	'juiz-last-tweet-widget' );
define( 'JUIZ_LTW_SETTING_NAME', 	'juiz_ltw_settings' );
define( 'JUIZ_LTW_SETTINGS_URL', 	admin_url('options-general.php?page='.JUIZ_LTW_SLUG) );



// uninstall hook

register_uninstall_hook( JUIZ_LTW_FILE, 'juiz_ltw_uninstaller' );
function juiz_ltw_uninstaller() {
	
	global $wpdb;
		
	// delete plugin options
	delete_option( JUIZ_LTW_SETTING_NAME );

	// delete widget option
	delete_option( 'widget_juiz_last_tweet_widget');
	
	// delete plugin feeds cache (options)
	$wpdb->query( 'DELETE FROM ' . $wpdb->options . ' WHERE option_name LIKE "jltw_%"' );

}

// activation hook

register_activation_hook( JUIZ_LTW_FILE, 'juiz_ltw_activation' );
function juiz_ltw_activation() {

	if( !$jltw_options = get_option( JUIZ_LTW_SETTING_NAME ) ) {
		update_option( JUIZ_LTW_SETTING_NAME, array(
			'consumer_key' 		=> '',
			'consumer_secret' 	=> '',
			'oauth_token'		=> '',
			'oauth_token_secret'=> '',
			'change_rss_feed'	=> 0,
			'default_styles'	=> 1,
			//for the next updates... chuuuut, keep it secret ;)
			'css_style_version'		=> 1,
			'show_nb_of_followers'	=> 0,
			'flat_design_bgcolor'	=> '',
			'links_colors'			=> array(
				'hastag'	=> '',
				'username'	=> '',
				'weblink'	=> ''
			)
		));
	}
}

// admin notice

add_action('admin_notices', 'juiz_ltw_admin_notices');
function juiz_ltw_admin_notices(){
	if ( $jltw_options = get_option( JUIZ_LTW_SETTING_NAME ) ) {
		if ($jltw_options['consumer_key']==''
			|| $jltw_options['consumer_secret']=='' 
			|| $jltw_options['oauth_token'] == '' 
			|| $jltw_options['oauth_token_secret'] == '') 
		{
			echo '<div class="error">
				<h3>'.__("Don't worry!",'juiz_ltw').'</h3>
				<p>'.sprintf(__('But you need to %scomplete the %sJuiz Last Tweet Widget%s options page%s if you want to display your latest tweets.','juiz_ltw'), '<a href="'.JUIZ_LTW_SETTINGS_URL.'">', '<strong>', '</strong>','</a>').'</p>
			</div>';
		}
	}
}


class Juiz_Last_Tweet_Widget extends WP_Widget {

	function Juiz_Last_Tweet_Widget() {
	
		// multilingual
		
		if(function_exists('load_plugin_textdomain')) {
			load_plugin_textdomain( 'juiz_ltw', false, JUIZ_LTW_DIRNAME . '/languages');
		}
		
		// action links setting
		
		add_filter( 'plugin_action_links_'.plugin_basename( JUIZ_LTW_FILE ), 'juiz_ltw_plugin_action_links',  10, 2);
		if ( !function_exists(' juiz_ltw_plugin_action_links')) {
			function juiz_ltw_plugin_action_links( $links, $file ) {
				$links[] = '<a href="'.admin_url('widgets.php').'">' . __('Widgets') .'</a>';
				$links[] = '<a href="'.JUIZ_LTW_SETTINGS_URL.'">' . __('Settings') .'</a>';
				return $links;
			}
		}

		// including options page
		require_once( 'admin/jltw-admin.inc.php' );

		$widget_ops = array(
			'classname' => 'juiz_last_tweet_widget',
			'description' => __('List you last tweet by displaying content, date, and link to follow you', 'juiz_ltw')
		);

		$control_ops = array();
		
		$this->WP_Widget('juiz_last_tweet_widget', __('Juiz Last Tweet', 'juiz_ltw'), $widget_ops, $control_ops);
	}

	function form($instance) {
	
		$instance = wp_parse_args((array) $instance, array(
			'juiz_last_tweet_title' => '',
			'juiz_last_tweet_username' => '',
			'juiz_last_tweet_no_tweets' => '1',
			'juiz_last_tweet_show_avatar' => false,
			'juiz_last_tweet_cache_duration' => 0,
			'juiz_last_tweet_action_links' => false,
			'juiz_last_tweet_auto_slide' => false,
			'juiz_last_tweet_auto_slide_delay' => 0,
			'juiz_last_tweet_own_css' => ''
		));
		
		$action_links_checked = $show_avatar_checked = $auto_slide_checked = ' checked="checked"';

		if ( $instance['juiz_last_tweet_action_links'] == false )
			$action_links_checked = '';
			
		if ( $instance['juiz_last_tweet_show_avatar'] == false )
			$show_avatar_checked = '';
			
		if ( $instance['juiz_last_tweet_auto_slide'] == false )
			$auto_slide_checked = '';
			
			

		// Version of the plugin (hidden field)
		$jzoutput  = '<input id="' . $this->get_field_id('plugin-version') . '" name="' . $this->get_field_name('plugin-version') . '" type="hidden" value="' . JUIZ_LTW_VERSION . '" />';

		// Title
		$jzoutput .= '
			<p style="border-bottom: 1px solid #DFDFDF;">
				<label for="' . $this->get_field_id('juiz_last_tweet_title') . '"><strong>' . __('Title', 'juiz_ltw') . '</strong></label>
			</p>
			<p>
				<input id="' . $this->get_field_id('juiz_last_tweet_title') . '" name="' . $this->get_field_name('juiz_last_tweet_title') . '" type="text" value="' . $instance['juiz_last_tweet_title'] . '" />
			</p>
		';

		// Settings
		$jzoutput .= '
			<p style="border-bottom: 1px solid #DFDFDF;"><strong>' . __('Preferences', 'juiz_ltw') . '</strong></p>
			
			<p>
				<label>' . __('Username', 'juiz_ltw') . '<br />
				<span style="color:#999;">@</span><input id="' . $this->get_field_id('juiz_last_tweet_username') . '" name="' . $this->get_field_name('juiz_last_tweet_username') . '" type="text" value="' . $instance['juiz_last_tweet_username'] . '" /> <abbr title="' . __('No @, just your username', 'juiz_ltw') . '">(?)</abbr></label>
			</p>
			<p>
				<label>' . __('Number of tweets to show', 'juiz_ltw') . '<br />
				<input style="margin-left: 1em;" id="' . $this->get_field_id('juiz_last_tweet_no_tweets') . '" name="' . $this->get_field_name('juiz_last_tweet_no_tweets') . '" type="text" value="' . $instance['juiz_last_tweet_no_tweets'] . '" /> <abbr title="' . __('Just a number, between 1 and 5 for example', 'juiz_ltw') . '">(?)</abbr></label>
			</p>
			<p>
				<label>' . __('Duration of cache', 'juiz_ltw') . '<br />
				<input style="margin-left: 1em; text-align:right;" id="' . $this->get_field_id('juiz_last_tweet_cache_duration') . '" name="' . $this->get_field_name('juiz_last_tweet_cache_duration') . '" type="text" size="10" value="' . $instance['juiz_last_tweet_cache_duration'] . '" /> '.__('Seconds', 'juiz_ltw').' <abbr title="' . __('A big number save your page speed. Try to use the delay between each tweet you make. (e.g. 1800 s = 30 min)', 'juiz_ltw') . '">(?)</abbr></label>
			</p>
			<p>
				<label>' . __('Show your avatar?', 'juiz_ltw') . ' 
				<input type="checkbox" name="' . $this->get_field_name('juiz_last_tweet_show_avatar') . '" id="' . $this->get_field_id('juiz_last_tweet_show_avatar') . '"'.$show_avatar_checked.' /> <abbr title="' . __("If it's possible, display your avatar at the top of tweets list", 'juiz_ltw') . '">(?)</abbr></label>
			</p>
			<p>
				<label>' . __('Show action links?', 'juiz_ltw') . ' 
				<input type="checkbox" name="' . $this->get_field_name('juiz_last_tweet_action_links') . '" id="' . $this->get_field_id('juiz_last_tweet_action_links') . '"'.$action_links_checked.' /> <abbr title="' . __("Display action links like Retweet, Reply and Fav", 'juiz_ltw') . '">(?)</abbr></label>
			</p>
			<p>
				<label>' . __('Auto slide one by one?', 'juiz_ltw') . ' 
				<input type="checkbox" name="' . $this->get_field_name('juiz_last_tweet_auto_slide') . '" id="' . $this->get_field_id('juiz_last_tweet_auto_slide') . '"'.$auto_slide_checked.' /> <abbr title="' . __("Use JavaScript to activate an little slider showing tweet by tweet", 'juiz_ltw') . '">(?)</abbr></label>
			</p>
			<p>
				<label>' . __('Delay between 2 tweets?', 'juiz_ltw') . ' 
				<input style="margin-left: 1em; text-align:right;" id="' . $this->get_field_id('juiz_last_tweet_auto_slide_delay') . '" name="' . $this->get_field_name('juiz_last_tweet_auto_slide_delay') . '" type="text" size="10" value="' . $instance['juiz_last_tweet_auto_slide_delay'] . '" /> '.__('Seconds', 'juiz_ltw').' <abbr title="' . __("Chose a delay if you use the auto slide feature.", 'juiz_ltw') . '">(?)</abbr></label>
			</p>
		';
		
		// Default & Own CSS
		$jzoutput .= '
			<p style="border-bottom: 1px solid #DFDFDF;"><strong>' . __('Manage CSS', 'juiz_ltw') . '</strong></p>
			<p>
				<label for="' . $this->get_field_id('juiz_last_tweet_own_css') . '" style="display:inline-block;">' . __('Your own CSS', 'juiz_ltw') . ':  <abbr title="' . __('Write your CSS here to replace or overwrite the default CSS', 'juiz_ltw') . '">(?)</abbr></label>
				<textarea id="' . $this->get_field_id('juiz_last_tweet_own_css') . '" rows="7" cols="30" name="' . $this->get_field_name('juiz_last_tweet_own_css') . '">' . $instance['juiz_last_tweet_own_css'] . '</textarea>
			</p>
		';
		
		echo $jzoutput;
	}

	function update($new_instance, $old_instance) {
		
		$instance = $old_instance;

		$new_instance = wp_parse_args((array) $new_instance, array(
			'juiz_last_tweet_title' => '',
			'juiz_last_tweet_username' => '',
			'juiz_last_tweet_no_tweets' => '1',
			'juiz_last_tweet_show_avatar' => false,
			'juiz_last_tweet_cache_duration' => 0,
			'juiz_last_tweet_action_links' => false,
			'juiz_last_tweet_auto_slide' => false,
			'juiz_last_tweet_auto_slide_delay' => 0,
			'juiz_last_tweet_own_css' => ''
		));

		$instance['plugin-version'] = strip_tags($new_instance['juiz_last_tweet-version']);
		$instance['juiz_last_tweet_title'] = strip_tags($new_instance['juiz_last_tweet_title']);
		$instance['juiz_last_tweet_username'] = strip_tags($new_instance['juiz_last_tweet_username']);
		$instance['juiz_last_tweet_no_tweets'] = strip_tags($new_instance['juiz_last_tweet_no_tweets']);
		$instance['juiz_last_tweet_show_avatar'] = strip_tags($new_instance['juiz_last_tweet_show_avatar']);
		$instance['juiz_last_tweet_cache_duration'] = $new_instance['juiz_last_tweet_cache_duration'];
		$instance['juiz_last_tweet_action_links'] = $new_instance['juiz_last_tweet_action_links'];
		$instance['juiz_last_tweet_auto_slide'] = $new_instance['juiz_last_tweet_auto_slide'];
		$instance['juiz_last_tweet_auto_slide_delay'] = $new_instance['juiz_last_tweet_auto_slide_delay'];
		$instance['juiz_last_tweet_own_css'] = $new_instance['juiz_last_tweet_own_css'];

		return $instance;
	}

	function widget($args, $instance) {
		extract($args);

		echo $before_widget;

		$title = (empty($instance['juiz_last_tweet_title'])) ? '' : apply_filters('widget_title', $instance['juiz_last_tweet_title']);

		if(!empty($title)) {
			echo $before_title . $title . $after_title;
		}

		echo $this->juiz_last_tweet_output($instance, 'widget');
		echo $after_widget;
	}

	function juiz_last_tweet_output($args = array(), $position) {
		
		
		$need_auto_slide_class = $data_delay = '';
		
		$the_username = $args['juiz_last_tweet_username'];
		$the_username = preg_replace('#^@(.+)#', '$1', $the_username);
		$the_nb_tweet = $args['juiz_last_tweet_no_tweets'];
		$need_cache = ($args['juiz_last_tweet_cache_duration']!='0') ? true : false;
		$show_avatar = ($args['juiz_last_tweet_show_avatar']) ? true : false;
		$show_action_links = ($args['juiz_last_tweet_action_links']) ? true : false;
		

		if ( $the_nb_tweet > 1 ) {
			$need_auto_slide_class = ($args['juiz_last_tweet_auto_slide']) ? ' juiz_ltw_autoslide' : '';
			if($args['juiz_last_tweet_auto_slide'])
				$data_delay = (intval($args['juiz_last_tweet_auto_slide_delay']) == 0) ? ' data-delay="7"' : ' data-delay="'.$args['juiz_last_tweet_auto_slide_delay'].'"';
		}


		
		/*
		 * change the default feed cache recreation period
		 */
		 
		if ( !function_exists ('juiz_ltw_filter_handler') ) {
			function juiz_ltw_filter_handler ( $seconds ) {
				return intval(60); //seconds
			}
		}
		add_filter( 'wp_feed_cache_transient_lifetime' , 'juiz_ltw_filter_handler' ); 

		
		 
		if ( !function_exists('jltw_format_since')) {
			function jltw_format_since ( $date ) {
				
				$temp = strtotime($date);
				
				if($temp != -1)
					$timestamp = $temp;
				else {
					// often PHP4 fail
					return false;
					exit;
				}
				
				$the_date = '';
				$now = time();
				$diff = $now - $timestamp;
				
				if($diff < 60 ) {
					$the_date .= $diff.' ';
					$the_date .= ($diff > 1) ?  __('Seconds', 'juiz_ltw') :  __('Second', 'juiz_ltw');
				}
				elseif($diff < 3600 ) {
					$the_date .= round($diff/60).' ';
					$the_date .= (round($diff/60) > 1) ?  __('Minutes', 'juiz_ltw') :  __('Minute', 'juiz_ltw');
				}
				elseif($diff < 86400 ) {
					$the_date .=  round($diff/3600).' ';
					$the_date .= (round($diff/3600) > 1) ?  __('Hours', 'juiz_ltw') :  __('Hour', 'juiz_ltw');
				}
				else {
					$the_date .=  round($diff/86400).' ';
					$the_date .= (round($diff/86400) > 1) ?  __('Days', 'juiz_ltw') :  __('Day', 'juiz_ltw');
				}
			
				return $the_date;
			}
		}
		if ( !function_exists('jltw_format_tweettext')) {
			function jltw_format_tweettext($raw_tweet, $username) {

				$target4a = apply_filters('juiz_ltw_target_attr', '_self'); // @filters

				$i_text = $raw_tweet;			
				//$i_text = htmlspecialchars_decode($raw_tweet);
				//$i_text = preg_replace('#(([a-zA-Z0-9_-]{1,130})\.([a-z]{2,4})(/[a-zA-Z0-9_-]+)?((\#)([a-zA-Z0-9_-]+))?)#','<a href="//$1">$1</a>',$i_text); 
				// replace tag
				$i_text = preg_replace('#\<([a-zA-Z])\>#','&lt;$1&gt;',$i_text);
				// replace ending tag
				$i_text = preg_replace('#\<\/([a-zA-Z])\>#','&lt;/$1&gt;',$i_text);
				// replace classic url
				$i_text = preg_replace('#(((https?|ftp)://(w{3}\.)?)(?<!www)(\w+-?)*\.([a-z]{2,4})(/[a-zA-Z0-9_\?\=-]+)?)#',' <a href="$1" rel="nofollow" class="juiz_last_tweet_url" target="'.$target4a.'">$5.$6$7</a>',$i_text);
				// replace user link
				$i_text = preg_replace('#@([a-zA-z0-9_]+)#i','<a href="http://twitter.com/$1" class="juiz_last_tweet_tweetos" rel="nofollow" target="'.$target4a.'">@$1</a>',$i_text);
				// replace hash tag search link ([a-zA-z0-9_] recently replaced by \S)
				$i_text = preg_replace('#[^&]\#(\S+)#i',' <a href="http://twitter.com/#!/search/?src=hash&amp;q=%23$1" class="juiz_last_tweet_hastag" rel="nofollow" target="'.$target4a.'">#$1</a>',$i_text); // old url was : /search/%23$1
				// remove start username
				$i_text = preg_replace( '#^'.$username.': #i', '', $i_text );
				
				return $i_text;
			
			}
		}
		if ( !function_exists('jltw_format_tweetsource')) {
			function jltw_format_tweetsource($raw_source) {
			
				$target4a = apply_filters('juiz_ltw_target_attr', '_self'); // @filters

				$i_source = htmlspecialchars_decode($raw_source);
				$i_source = preg_replace('#^web$#','<a href="http://twitter.com" rel="nofollow" target="'.$target4a.'">Twitter</a>', $i_source);
				
				return $i_source;
			
			}
		}
		if ( !function_exists('jltw_get_the_user_timeline')) {
			function jltw_get_the_user_timeline($username, $nb_tweets, $show_avatar, $show_action_links, $cache_delay) {

				$html_result = '';
				$cache_delay = ($cache_delay == 0 ) ? 1 : $cache_delay;
				$jltw_html_option = 'jltw_html_'.strtolower($username).'_'.$nb_tweets.'_'.$cache_delay;
				$jltw_timer_option = 'jltw_timer_'.strtolower($username).'_'.$nb_tweets.'_'.$cache_delay;

				// check if we have transient (cache of HTML)
				// for multiblog support, maybe use the get_current_blog_id() function to add it in option name ? or not...
				$current_timer = get_option( $jltw_timer_option , false);
				
				if ( !$current_timer ) {
					// create option
					add_option( $jltw_html_option , '', '', 'yes');
					add_option( $jltw_timer_option , (time() + intval($cache_delay)), '', 'yes');
				}
				elseif ( $current_timer AND $current_timer > time() ) {
					// get the cached HTML
					$html_result = get_option( $jltw_html_option, false );
				}
				
				// to find is cached html are tweets
				$is_tweet_cached = preg_match('#juiz_lt_content#',$html_result) ? true : false;

				// if need update
				if (!$current_timer OR $current_timer <= time()) {

					$username = (empty($username)) ? 'geoffrey_crofte' : $username;
					$nb_tweets = (empty($nb_tweets) OR $nb_tweets == 0) ? 1 : $nb_tweets;
					$search_feed1 = $search_feed2 = '';
					$is_api_1_1 = $the_best_feed = false;

					// new API 1.1
					if ( !class_exists('TwitterOAuth')) {
						require_once ('inc/twitteroauth.php');
					}
					
					$options = get_option( JUIZ_LTW_SETTING_NAME );

					$consumer_key 		= $options['consumer_key'];
					$consumer_secret 	= $options['consumer_secret'];
					$oauth_token 		= $options['oauth_token'];
					$oauth_token_secret = $options['oauth_token_secret'];

					$connection = new TwitterOAuth($consumer_key, $consumer_secret, $oauth_token, $oauth_token_secret);

					$search_feed3 = "https://api.twitter.com/1.1/statuses/user_timeline.json?screen_name=".$username."&count=".intval($nb_tweets); 
					$api_1_1_content = $connection->get($search_feed3);

					if (is_array($api_1_1_content) AND isset($api_1_1_content[0] -> id)) {
						$is_api_1_1 = true;
					}
					else {
						if (isset($api_1_1_content->errors[0] -> code)) echo '<!-- JLTW Twitter API 1.1 error code : '. $api_1_1_content->errors[0] -> code . ' ('. $api_1_1_content->errors[0] -> message . ')-->';
						// include of WP's feed functions
						include_once(ABSPATH . WPINC . '/feed.php');
						
						// if this option if checked...
						$first_feed = $options['change_rss_feed'];
						// reverse feed1 and feed2, and keep fallback...
						$search_feed1 = $first_feed ? "http://search.twitter.com/search.rss?q=from%3A".$username."&rpp=".intval($nb_tweets) : "http://api.twitter.com/1/statuses/user_timeline.rss?screen_name=".$username."&count=".intval($nb_tweets);
						$search_feed2 = $first_feed ? "http://api.twitter.com/1/statuses/user_timeline.rss?screen_name=".$username."&count=".intval($nb_tweets) : "http://search.twitter.com/search.rss?q=from%3A".$username."&rpp=".intval($nb_tweets);
					
						// get the better feed
						// try with the first one
						
						$sf_rss = fetch_feed ( $search_feed1 );
						if ( is_wp_error($sf_rss) ) {
							// if first one is not ok, try with the second one
							$sf_rss = fetch_feed ( $search_feed2 );
							
							if ( is_wp_error($sf_rss) ) $the_best_feed = false;
							else $the_best_feed = '2';
						}
						else $the_best_feed = '1';
						
						// if one of them is readable, check if we have tweets (thank you Twitter =_=)
						if ( $the_best_feed ) {
							
							// in case of...
							// if we already have one tweet at least (finded with the juiz_lt_content class), keep those tweet, don't show message error.
							$twitter_fail = $is_tweet_cached ? $html_result : apply_filters('juiz_ltw_twitter_has_a_problem',__('Twitter has a problem with your RSS feed&hellip;', 'juiz_ltw'));
						
							$max_i = $sf_rss -> get_item_quantity($nb_tweets);
							
							// if the first feed return zero item, and if the feed is not already the second one, try with the second
							if ( $max_i == 0) {
								if ($the_best_feed!='2') {
									$sf_rss = fetch_feed ( $search_feed2 );
									
									if ( !is_wp_error($sf_rss) ) {
										$max_i = $sf_rss -> get_item_quantity($nb_tweets);
										if ( $max_i != 0 ) $the_best_feed = true;
										else {
											$html_result = $twitter_fail;
											$the_best_feed = false;
										}
									}
									else {
										$html_result = $twitter_fail;
										$the_best_feed = false;
									}
								}
								else {
									$html_result = $twitter_fail;
									$the_best_feed = false;
								}
							}
							else {
								// all right
								$the_best_feed = true;
							}
							
						}
						// end of big backup control

					} // end of "if API 1.1" (array) or "API 1.0" (feed)


					// if one of the rss is readable
					// or if API 1.1 has something returned
					if ( $the_best_feed OR $is_api_1_1 ) {

						$rss_i = $is_api_1_1 ? $api_1_1_content : $sf_rss -> get_items(0, $max_i);

						$i = 0;

						foreach ( $rss_i as $tweet ) {
							
							$author = $i_source = $avatar = $html_avatar = $new_attrs = '';

							$i++;

							$i_title = $is_api_1_1 ? jltw_format_tweettext($tweet -> text, $username) : jltw_format_tweettext($tweet -> get_title() , $username);
							$i_creat = $is_api_1_1 ? jltw_format_since( $tweet -> created_at ) : jltw_format_since( $tweet -> get_date() );
							
							$i_guid = $is_api_1_1 ? "http://twitter.com/".$tweet -> user -> screen_name."/status/".$tweet -> id_str : $tweet -> get_link();

							if ( $is_api_1_1 ) {
								$author = $tweet -> user -> screen_name;
							}
							else {
								$author_tag = $tweet -> get_item_tags('','author');
								$author_a = $author_tag[0]['data'];
								$author = substr($author_a, 0, stripos($author_a, "@") );
							}
							
							if ( $is_api_1_1 ) {
								$i_source = '<span class="juiz_ltw_source">'.__('via','jltw_lang').' '. jltw_format_tweetsource( $tweet -> source ) . '</span>';
							}
							else {
								$source_tag = $tweet -> get_item_tags('http://api.twitter.com','source');
								$i_source = $source_tag[0]['data'];
								$i_source = jltw_format_tweetsource($i_source);
								$i_source = ($i_source) ? '<span class="juiz_ltw_source">'.__('via','jltw_lang').' ' . $i_source . '</span>' : '';
							}
							
							if ( $the_best_feed == false && $show_avatar ) {
								$avatar = $tweet -> user -> profile_image_url;
							}
							elseif ( $the_best_feed == '1' && $show_avatar) {
								$avatar = "http://api.twitter.com/1/users/profile_image/". $username .".xml?size=normal"; // or bigger
							}
							elseif ($the_best_feed == '2' && $show_avatar) {
								$avatar_tag = $tweet->get_item_tags('http://base.google.com/ns/1.0','image_link');
								$avatar = $avatar_tag[0]['data'];
							}

							if ($i==1 && $show_avatar && $avatar) { 
								$avatar_attr = array(
									'title'		 => __('Follow', 'juiz_ltw') . ' @'.$username.' ' . __('on twitter.', 'juiz_ltw'),
									'href'		 => esc_url( 'http://twitter.com/' . $username ),
									'src'		 => esc_url( $avatar ),
									'alt'		 => $author,
									'width'		 => '48',
									'height'	 => '48',
									'aria-hidden'=> 'true'
								);
								
								$avatar_attr = apply_filters('juiz_ltw_user_avatar_attr', $avatar_attr); // @filters
								if(isset($avatar_attr['attrs'])) {
									foreach ( $avatar_attr['attrs'] as $k=>$v)
										$new_attrs .= ' '.$k.'="'.$v.'"';  
								}
								
								$target4a = apply_filters('juiz_ltw_target_attr', '_self'); // @filters

								$html_avatar = '<span class="user_avatar" aria-hidden="'.$avatar_attr['aria-hidden'].'"><a href="'. $avatar_attr['href'] .'" title="' . $avatar_attr['title'] . '" target="'.$target4a.'"><img src="'. $avatar_attr['src'] .'" alt="'. $avatar_attr['alt'] .'" width="'.$avatar_attr['width'].'" height="'.$avatar_attr['height'].'"'.$new_attrs.' /></a></span>';
							}
							
							$html_avatar = apply_filters('juiz_ltw_user_avatar', $html_avatar); // @filters
							
							
							//time ago filters
							$the_time_ago = array(
								'before'	=> __('Time ago', 'juiz_ltw'),
								'after'		=> '',
								'content'	=> __('See the status', 'juiz_ltw')
							);
							
							$the_time_ago = apply_filters('juiz_ltw_time_ago', $the_time_ago); // @filters
							
							// for PHP4 fail with strtotime() function

							$target4a = apply_filters('juiz_ltw_target_attr', '_self'); // @filters

							$time_ago = ($i_creat!=false) ?  $the_time_ago['before'] . ' <a href="'. esc_url( $i_guid ) .'" target="'.$target4a.'" title="'.$the_time_ago['content'].'">' . $i_creat . '</a>' . $the_time_ago['after'] : '<a href="'. esc_url( $i_guid ) .'" target="'.$target4a.'">' . $the_time_ago['content'] .'</a>';

							// action links
							
							$juiz_tweet_id = $is_api_1_1 ? $tweet-> id_str : preg_replace('#(((https?)://(w{3}\.)?)(?<!www)(\w+-?)*\.([a-z]{2,4})(/[a-zA-Z0-9_\?\=-]+)?(/[a-zA-Z0-9_\?\=-]+)?/([0-9]{10,}))#','$9',$i_guid);

							$html_action_links = '';
							if ($show_action_links) {
								$target4action_links = apply_filters('juiz_ltw_target_action_links_attr', '_blank'); // @filters
								$html_action_links ='<span class="juiz_action_links">
									<a title="'.__('Reply', 'juiz_ltw').'" href="http://twitter.com/intent/tweet?in_reply_to='.$juiz_tweet_id.'" class="juiz_al_reply" rel="nofollow" target="'.$target4action_links.'">'.__('Reply', 'juiz_ltw').'</a> <span class="juiz_ltw_sep">-</span>
									<a title="'.__('Retweet', 'juiz_ltw').'" href="http://twitter.com/intent/retweet?tweet_id='.$juiz_tweet_id.'" class="juiz_al_retweet" rel="nofollow" target="'.$target4action_links.'">'.__('Retweet', 'juiz_ltw').'</a> <span class="juiz_ltw_sep">-</span>
									<a title="'.__('Favorite', 'juiz_ltw').'" href="http://twitter.com/intent/favorite?tweet_id='.$juiz_tweet_id.'" class="juiz_al_fav" rel="nofollow" target="'.$target4action_links.'">'.__('Favorite', 'juiz_ltw').'</a> 
								</span>';
							}

							$li = apply_filters('juiz_ltw_each_item_tag', 'li'); // @filters

							$hint_class = $is_api_1_1 ? ' jltw_api_1_1' : ' jltw_feed_'.$the_best_feed;

							$item_pos_class = " jltw_item_alone";
							if ($nb_tweets > 1) {
								switch ($i) {
									case 1;
										$item_pos_class = " jltw_item_first";
										break;
									case $nb_tweets;
										$item_pos_class = " jltw_item_last";
										break;
									default;
										$item_pos_class = " jltw_item_".$i;
										break;
								}
							}
							
							$html_result_temp = '
								<'.$li.' class="juiz_last_tweet_item'.$hint_class.$item_pos_class.'">
									'.$html_avatar.'
									<span class="juiz_lt_content">' . $i_title . '</span>
									<span class="juiz_last_tweet_footer_item">
										<em class="juiz_last_tweet_inner juiz_last_tweet_metadata">  
											'.$time_ago .' '. $i_source .'
										</em>
										'.$html_action_links.'
									</span>
								</'.$li.'>
							';
							
							$html_result .= apply_filters('juiz_ltw_each_tweet', $html_result_temp); // @filters
						}
					}
					// if any feed is readable
					else {
						// if we already have tweets, don't use error message
						if( !$is_tweet_cached ) {
							$html_result = '<li><em>' . $html_result . ' '.apply_filters('juiz_ltw_twitter_feed_not_loadable',__('The RSS feed for this twitter account is not loadable for the moment.', 'juiz_ltw')).'</em></li>';
						}
					}
					
					// set html cache options
					update_option( $jltw_html_option , $html_result);
					update_option( $jltw_timer_option , (time() + intval( $cache_delay )));
					
				} // end of "if need update"

				
				// at the end, return html content
				return $html_result;
			}
		}
			
			$ul = apply_filters('juiz_ltw_list_container_tag', 'ul'); // @filters
			
			// display the widget front content (but not immediatly because of cache system)
			$juiz_ltw_all_tweets= '
				<div'.$data_delay.' class="juiz_last_tweet_inside'.$need_auto_slide_class.'">
					<'.$ul.' class="juiz_last_tweet_tweetlist">
						'. jltw_get_the_user_timeline($the_username, $the_nb_tweet, $show_avatar, $show_action_links, $args['juiz_last_tweet_cache_duration']) .'
					</'.$ul.'>
					
					<p class="juiz_last_tweet_follow_us">
						<span class="juiz_ltw_follow">' . __('Follow', 'juiz_ltw') . '</span>
						<a class="juiz_ltw_username" href="' . esc_url( 'http://twitter.com/' . $the_username ) . '">@' . $the_username . '</a>
						<span class="juiz_ltw_ontwitter">' . __('on twitter.', 'juiz_ltw') . '</span>
					</p>
				</div>
			';

			// if JS slider is needed by widget
			if($need_auto_slide_class!='')
				wp_enqueue_script('juiz_ltw_auto_slide', plugins_url('/js/juiz_ltw_auto_slide.min.js', __FILE__), array('jquery'), JUIZ_LTW_VERSION);
			
			echo apply_filters('juiz_ltw_content', $juiz_ltw_all_tweets); // @filters
	} // end of output
	
} // end of Widget extend

add_action('widgets_init', create_function('', 'return register_widget("Juiz_Last_Tweet_Widget");'));

/**
 * Custom styles, <del>JS</del> and Shortcode
 */
 if(!is_admin()) {

 	add_action('wp_enqueue_scripts', 'jltw_add_default_style');
 	if (!function_exists('jltw_add_default_style')) {
 		function jltw_add_default_style() {
 			$options = get_option( JUIZ_LTW_SETTING_NAME );
 			if ( $options['default_styles'] ) {
 				wp_enqueue_style('juiz_last_tweet_widget', plugins_url(JUIZ_LTW_DIRNAME."/css/juiz_last_tweet.css", array(), JUIZ_LTW_VERSION, 'all' ));
 			}
 		}
 	}

 	// custom head
	add_action('wp_head', 'juiz_last_tweet_head');
	if( !function_exists('juiz_last_tweet_head') ) {
		function juiz_last_tweet_head() {

			$juiz_last_tweet_css = '';
			$var_sOwnCSS = '';
			
			$array_widgetOptions = get_option('widget_juiz_last_tweet_widget');
			
			if(is_array($array_widgetOptions)) {
				foreach($array_widgetOptions as $key => $value) {
					if($value['juiz_last_tweet_own_css'])
						$var_sOwnCSS = $value['juiz_last_tweet_own_css'];
				}

				if ( $var_sOwnCSS != '' ) {
					$juiz_last_tweet_css .= '
						<style type="text/css">
							<!--
							'  . $var_sOwnCSS . '
							-->
						</style>
					';
				}
			}
			echo $juiz_last_tweet_css;
		}
	}
	// custom footer
	add_action('wp_footer', 'juiz_last_tweet_footer');
	if( !function_exists('juiz_last_tweet_footer') ) {
		function juiz_last_tweet_footer() {
			$var_custom_juiz_scripts = "\n\n".'<!-- No script for Juiz Last Tweet Widget :) -->'."\n\n";
			echo $var_custom_juiz_scripts;
		}
	}
	
	
	
	/*
	 * Add shortcode
	 */
	if ( !function_exists('sc_4_jltw')) {

		global $jltw_id;
		$jltw_id = 0;

		function sc_4_jltw($atts) {
		
			global $wp_widget_factory, $jltw_id;
			
			$atts = shortcode_atts(array(
				'username' 	=> 'geoffrey_crofte',
				'nb' 		=> '1',
				'avatar' 	=> 0, // false
				'cache' 	=> 0,
				'transition'=> 0, // false
				'delay'		=> 0,
				'links'		=> 0 // false
			), $atts);
			
			
			
			
			$instance = array(); 
			
			$instance['juiz_last_tweet_username'] 			= esc_attr(strip_tags($atts['username']));
			$instance['juiz_last_tweet_no_tweets'] 			= (int)  $atts['nb'];
			$instance['juiz_last_tweet_show_avatar']		= (bool) $atts['avatar'];
			$instance['juiz_last_tweet_cache_duration'] 	= (int)  $atts['cache'];
			$instance['juiz_last_tweet_auto_slide']			= (bool) $atts['transition'];
			$instance['juiz_last_tweet_auto_slide_delay']	= (int)  $atts['delay'];
			$instance['juiz_last_tweet_action_links']		= (bool) $atts['links'];
			
			$widget_name = "Juiz_Last_Tweet_Widget";
			
			if (!is_a($wp_widget_factory->widgets[$widget_name], 'WP_Widget')):
				$wp_class = 'WP_Widget_'.ucwords(strtolower($class));
				
				if (!is_a($wp_widget_factory->widgets[$wp_class], 'WP_Widget')):
					return '<p>'.sprintf(__("%s: Widget class not found.", "juiz_ltw"),'<strong>'.$class.'</strong>').'</p>';
				else:
					$class = $wp_class;
				endif;
			endif;
			
			ob_start();
			the_widget($widget_name, $instance, array(
				'widget_id'=>'arbitrary-instance-'.$jltw_id,
				'before_widget' => '',
				'after_widget' => '',
				'before_title' => '',
				'after_title' => ''
			));
			$output = ob_get_contents();
			ob_end_clean();
			$jltw_id++;
			return $output;
		}
		add_shortcode('jltw','sc_4_jltw');
		add_shortcode('tweets','sc_4_jltw');
	}
 
	if( !function_exists('get_the_tweets') ) {
		function get_the_tweets( $args ) {
			if( !function_exists('get_jltw') ) {
				return get_jltw( $args );
			}
		}
	}
	if( !function_exists('get_the_tweets') ) {
		function get_the_tweets( $args ) {
			if( !function_exists('get_jltw') ) {
				echo get_jltw( $args );
			}
		}
	}
	if( !function_exists('jltw') ) {
		function jltw( $args ) {
			echo get_jltw( $args );
		}
	}
	if( !function_exists('get_jltw') ) {
		function get_jltw ($args = array('username'=>'geoffrey_crofte', 'nb_tweets'=>1, 'avatar'=>false, 'cache'=>120, 'transition'=>false, 'delay'=>8, 'links'=>true)) {
			$avatar 	= $args['avatar'] 		? 1 : 0;
			$transition = $args['transition']	? 1 : 0;
			$links 		= $args['links']		? 1 : 0;
			$username	= $args['username']		? $args['username'] : 'geoffrey_crofte';
			$nb_tweets	= $args['nb_tweets']	? (int)$args['nb_tweets'] : 1;
			$cache 		= $args['cache']		? (int)$args['cache'] : 120;
			$delay 		= $args['delay']		? (int)$args['delay'] : '';

			return do_shortcode('[jltw username="'.$username.'" nb="'.$nb_tweets.'" avatar="'.$avatar.'" cache="'.$cache.'" transition="'.$transition.'" delay="'.$delay.'" links="'.$links.'"]');

		}
	}
	
}
?>
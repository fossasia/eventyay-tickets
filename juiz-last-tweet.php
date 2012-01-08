<?php
/**
 * Plugin Name: Juiz Last Tweet Widget
 * Plugin URI: http://www.creativejuiz.fr/blog/
 * Description: Adds a widget to your blog's sidebar to show your latest tweets. (XHTML-valid - No JS used to load tweets)
 * Author: Geoffrey Crofte
 * Version: 1.0.0 beta
 * Author URI: http://crofte.fr
 * License: GPLv2 or later 
 */

/**
 * = 1.0.0 beta =
 * Initial Release
 */
 
 /*

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

*/

define('JUIZ_LTW_VERSION', '1.0.0');

class Juiz_Last_Tweet_Widget extends WP_Widget {

	function Juiz_Last_Tweet_Widget() {
	
		if(function_exists('load_plugin_textdomain')) {
			load_plugin_textdomain('juiz_ltw', PLUGINDIR . '/' . dirname(plugin_basename(__FILE__)) . '/languages', dirname(plugin_basename(__FILE__)) . '/languages');
		}

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
			'juiz_last_tweet_cache_duration' => 1800,
			'juiz_last_tweet_default_css' => true
		));
		
		$default_css_checked = ' checked="checked"';
		if ( $instance['juiz_last_tweet_default_css'] == false )
			$default_css_checked = '';
			

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
			<p style="clear:both;"></p>
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
				<input style="margin-left: 1em;" id="' . $this->get_field_id('juiz_last_tweet_cache_duration') . '" name="' . $this->get_field_name('juiz_last_tweet_cache_duration') . '" type="text" size="10" value="' . $instance['juiz_last_tweet_cache_duration'] . '" /> '.__('Seconds', 'juiz_ltw').' <abbr title="' . __('A big number save your page speed. Try to use the delay between each tweet you make. (default is half hour : 1800 s)', 'juiz_ltw') . '">(?)</abbr></label>
			</p>
			
			<p style="clear:both;"></p>
		';
		
		// Default & Own CSS
		$jzoutput .= '
			<p style="border-bottom: 1px solid #DFDFDF;"><strong>' . __('Manage CSS', 'juiz_ltw') . '</strong></p>
			
			<p>
				<label>' . __('Use the default CSS ?', 'juiz_ltw') . ' 
				<input type="checkbox" name="' . $this->get_field_name('juiz_last_tweet_default_css') . '" id="' . $this->get_field_id('juiz_last_tweet_default_css') . '"'.$default_css_checked.' /> <abbr title="' . __('Load a little CSS file with default styles for the widget', 'juiz_ltw') . '">(?)</abbr></label>
			</p>
			<p>
				<label for="' . $this->get_field_id('juiz-ltw-own-css') . '" style="display:inline-block;">' . __('Your own CSS', 'juiz_ltw') . ':  <abbr title="' . __('Write your CSS here to replace or overwrite the default CSS', 'juiz_ltw') . '">(?)</abbr></label>
				<textarea id="' . $this->get_field_id('juiz-ltw-own-css') . '" rows="7" cols="30" name="' . $this->get_field_name('juiz-ltw-own-css') . '">' . $instance['juiz-ltw-own-css'] . '</textarea>
			</p>
		
			<p style="clear:both;"></p>
			<p style="clear:both;"></p>
		';
		
		echo $jzoutput;
	}

	function update($new_instance, $old_instance) {
		
		$instance = $old_instance;

		$new_instance = wp_parse_args((array) $new_instance, array(
			'juiz_last_tweet_title' => '',
			'juiz_last_tweet_username' => '',
			'juiz_last_tweet_no_tweets' => '1',
			'juiz_last_tweet_cache_duration' => 1800,
			'juiz_last_tweet_default_css' => true
		));

		$instance['plugin-version'] = strip_tags($new_instance['juiz_last_tweet-version']);
		$instance['juiz_last_tweet_title'] = strip_tags($new_instance['juiz_last_tweet_title']);
		$instance['juiz_last_tweet_username'] = strip_tags($new_instance['juiz_last_tweet_username']);
		$instance['juiz_last_tweet_no_tweets'] = strip_tags($new_instance['juiz_last_tweet_no_tweets']);
		$instance['juiz_last_tweet_cache_duration'] = strip_tags($new_instance['juiz_last_tweet_cache_duration']);
		$instance['juiz_last_tweet_default_css'] = strip_tags($new_instance['juiz_last_tweet_default_css']);
		$instance['juiz-ltw-own-css'] = $new_instance['juiz-ltw-own-css'];

		print_r($instance);

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
		
		/*debut du cache*/
		$cache_file = PLUGINDIR . '/' . dirname(plugin_basename(__FILE__)) . '/cache/index.html';
		$expire = time() - intval($args['juiz_last_tweet_cache_duration']);
		 
		if(file_exists($cache_file) && filemtime($cache_file) > $expire)
			readfile($cache_file);

		else {
		
			//add4cache
			ob_start(); // ouverture tampon
		
			function juiz_format_since($timestamp){
				
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
			
			
			function juiz_read_rss($file,$objects) {

				// read all the file
				if($string = @implode("",@file($file))) {

					// split the string in items
					$tmp = preg_split("/<\/?"."item".">/",$string);

					// for each item
					for($i=1;$i<sizeof($tmp)-1;$i+=2)

						// we read each of those objects
						foreach($objects as $obj) {

							// we split the string to obtain the content of the object
							$tmp2 = preg_split("/<\/?".$obj.">/",$tmp[$i]);

							// we add the content of the object to the results array
							$resultat[$i-1][] = @$tmp2[1];
						}

					// on retourne le tableau resultat
					return $resultat;
				}
			}
			
			function url_exists($url) {
				$hdrs = @get_headers($url);
				return is_array($hdrs) ? preg_match('/^HTTP\\/\\d+\\.\\d+\\s+2\\d\\d\\s+.*$/',$hdrs[0]) : false;
			} 
			
			function get_informations_xml_last_tweet($username, $nb_tweets) {
				
				$username = (empty($username)) ? 'geoffrey_crofte' : $username;
				$nb_tweets = (empty($nb_tweets) OR $nb_tweets == 0) ? 1 : $nb_tweets;
				$xml_result = '';
				
				// if the RSS file is loaded (exists ou readable)
				if ( !url_exists('http://twitter.com/statuses/user_timeline/'.$username.'.rss?count='.intval($nb_tweets))) {
					echo '<em>'.__('The RSS feed for this twitter account is not loadable for the moment.', 'juiz_ltw').'</em>';
					return;
				}
				
				$xml_infos = juiz_read_rss('http://twitter.com/statuses/user_timeline/'.$username.'.rss?count='.intval($nb_tweets), array('pubDate','title','guid','twitter:source'));
				
				if($xml_infos) {

					foreach($xml_infos as $item) {
					
						$i_creat = strtotime($item[0]);
						$i_title = htmlspecialchars_decode($item[1]);
						$i_title = preg_replace('#(((https?|ftp)://(w{3}\.)?)(?<!www)(\w+-?)*\.([a-z]{2,4})(/[a-zA-Z0-9_-]+)?)#',' <a href="$1" class="juiz_last_tweet_url">$1</a>',$i_title);
						$i_title = preg_replace('#@([a-zA-z0-9_]+)#i','<a href="http://twitter.com/$1" class="juiz_last_tweet_tweetos">@$1</a>',$i_title);
						$i_title = preg_replace('#[^&]\#([a-zA-z0-9_]+)#i',' <a href="http://twitter.com/search?q=#$1" class="juiz_last_tweet_hastag">#$1</a>',$i_title);
						$i_title = preg_replace( '#^'.$username.': #i', '', $i_title );
						$i_guid = $item[2];
						$i_source = htmlspecialchars_decode($item[3]);
					
					
						/* $i_title = preg_replace( '#'.$username.': #', '', $i_title ); */
					
						$xml_result .= '
							<li>
								<span class="juiz_lt_content">' . $i_title . '</span>
								<em class="juiz_last_tweet_inner">' . __('Time ago', 'juiz_ltw') . '
									<a href="'.$i_guid .'" target="_blank">' . juiz_format_since( $i_creat ) . '</a>
									via ' . $i_source . '
								</em>
							</li>
						';
					}
				}
				
				return $xml_result;
			}
			
			// display the widget front content (but not immediatly because of cache system)
			
			echo '
				<div class="juiz_last_tweet_inside">
					<ul id="juiz_last_tweet_tweetlist">
						'. get_informations_xml_last_tweet($args['juiz_last_tweet_username'], $args['juiz_last_tweet_no_tweets']) .'
					</ul>
					
					<p class="juiz_last_tweet_follow_us">
						' . __('Follow', 'juiz_ltw') . '
						<a href="http://twitter.com/' . $args['juiz_last_tweet_username'] . '">@' . $args['juiz_last_tweet_username'] . '</a>
						' . __('on twitter.', 'juiz_ltw') . '
					</p>
				</div>
			';
			
			// save informations
			$the_last_tweets = ob_get_contents();
			ob_end_clean(); // stop cache system
				
			file_put_contents($cache_file, $the_last_tweets) ; // write last tweets in the $cache_file
			echo $the_last_tweets ; // on affiche notre page :D 
		}
	}
}

add_action('widgets_init', create_function('', 'return register_widget("Juiz_Last_Tweet_Widget");'));

/**
 * Custom styles et JS
 */
 if(!is_admin()) {
	 
	//wp_enqueue_script('jquery');

	function juiz_last_tweet_head() {

		$juiz_last_tweet_css = '';
		
		$array_widgetOptions = get_option('widget_juiz_last_tweet_widget');
		$var_sOwnCSS = $array_widgetOptions[2]['juiz-ltw-own-css'];
		$use_default_css = $array_widgetOptions[2]['juiz_last_tweet_default_css'];
		
		if ( $use_default_css )
			$juiz_last_tweet_css .= '<link type="text/css" media="all" rel="stylesheet" id="juiz_last_tweet_widget_styles" href="'. plugins_url(dirname(plugin_basename(__FILE__))."/css/juiz_last_tweet.css") . '" />';

		if ( $var_sOwnCSS != '' ) {
			$juiz_last_tweet_css .= '
				<style type="text/css">
					<!--
					'  . $var_sOwnCSS . '
					-->
				</style>
			';
		}
		
		echo $juiz_last_tweet_css;
	}

	function juiz_last_tweet_footer() {
		$var_custom_juiz_scripts = "\n\n".'<!-- No script for Juiz Last Tweet widget :) -->'."\n\n";
		echo $var_custom_juiz_scripts;
	}

	// custom head and footer
	add_action('wp_head', 'juiz_last_tweet_head');
	add_action('wp_footer', 'juiz_last_tweet_footer');
}
?>
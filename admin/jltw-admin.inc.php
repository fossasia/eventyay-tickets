<?php
/*
 * Options page
 */
 

// Settings page in admin menu

add_action('admin_menu', 'add_juiz_ltw_settings_page');
function add_juiz_ltw_settings_page() {
	add_submenu_page( 
		'options-general.php', 
		__('Last Tweet Widget', 'juiz_ltw'),
		__('Last Tweet Widget', 'juiz_ltw'),
		'administrator',
		JUIZ_LTW_SLUG ,
		'juiz_ltw_settings_page' 
	);
}

// Some styles for settings page in admin
add_action( 'admin_head-settings_page_'.JUIZ_LTW_SLUG, 'juiz_ltw_custom_admin_header');
function juiz_ltw_custom_admin_header() {
	include_once ('jltw-admin-styles-scripts.php');

	// checking in this plugin page only, if options exist
	if( !$jltw_options = get_option( JUIZ_LTW_SETTING_NAME ) ) {
		update_option( JUIZ_LTW_SETTING_NAME, array(
			'consumer_key' 			=> '',
			'consumer_secret' 		=> '',
			'oauth_token'			=> '',
			'oauth_token_secret'	=> '',
			'change_rss_feed'		=> 0,
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


/*
 *****
 ***** Sections and fields for settings
 *****
 */

function add_juiz_ltw_plugin_options() {
	// all options in single registration as array
	register_setting( JUIZ_LTW_SETTING_NAME, JUIZ_LTW_SETTING_NAME, 'juiz_ltw_sanitize' );
	
	add_settings_section('juiz_ltw_plugin_twitter_api', __('Twitter API 1.1 Settings','juiz_ltw'), 'juiz_ltw_section_text', JUIZ_LTW_SLUG);
	
	add_settings_field('juiz_ltw_twitter_user', __('Consumer Key', 'juiz_ltw') , 'juiz_ltw_setting_input_consumer_key', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_twitter_api');
	add_settings_field('juiz_ltw_consumer_secret', __('Consumer Secret', 'juiz_ltw') , 'juiz_ltw_setting_input_consumer_secret', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_twitter_api');
	add_settings_field('juiz_ltw_oauth_token', __('oAuth Token', 'juiz_ltw') , 'juiz_ltw_setting_input_oauth_token', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_twitter_api');
	add_settings_field('juiz_ltw_oauth_token_secret', __('oAuth Token Secret', 'juiz_ltw') , 'juiz_ltw_setting_input_oauth_token_secret', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_twitter_api');

	add_settings_section('juiz_ltw_plugin_general', __('General settings','juiz_ltw'), 'juiz_ltw_section_text_general', JUIZ_LTW_SLUG);
	add_settings_field('juiz_ltw_rss_change', __('Use default appareance/styles?', 'juiz_ltw'), 'juiz_ltw_setting_radio_default_style', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_general');

	add_settings_section('juiz_ltw_plugin_fallback', __('Fallback Settings','juiz_ltw'), 'juiz_ltw_section_text_fallback', JUIZ_LTW_SLUG);
	add_settings_field('juiz_ltw_rss_change', __('Change RSS used (if you have bugs)', 'juiz_ltw'), 'juiz_ltw_setting_radio_rss_change', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_fallback');


}
add_filter('admin_init','add_juiz_ltw_plugin_options');


// sanitize posted data

function juiz_ltw_sanitize($options) {
	$newoptions['change_rss_feed'] 		= $options['change_rss_feed']==1 ? 1 : 0;
	$newoptions['default_styles']		= $options['default_styles']==1 ? 1 : 0;
	$newoptions['consumer_key']			= sanitize_text_field( $options['consumer_key'] );
	$newoptions['consumer_secret']		= sanitize_text_field( $options['consumer_secret'] );
	$newoptions['oauth_token']			= sanitize_text_field( $options['oauth_token'] );
	$newoptions['oauth_token_secret']	= sanitize_text_field( $options['oauth_token_secret'] );
	
	return $newoptions;
}

// first section text
function juiz_ltw_section_text() {
	echo '<p class="juiz_ltw_section_intro">'. __('You need to create a Twitter plugin to use Juiz Last Tweet Widget because of new API 1.1 rules of Twitter.', 'juiz_ltw') .' <button type="button" class="button juiz_how_to">'.__('How to?','juiz_ltw').'</button></p>';
	echo '<ol class="juiz_ltw_section_intro">';
	echo '<li>'.sprintf(__('Go to the %sTwitter Developer Center%s to create an app, and create an account if necessary (you can use your Twitter account)','juiz_ltw'),'<a href="https://dev.twitter.com/apps/new" target="_blank">','</a>').'</li>';
	echo '<li>'.__('Give it a name, description and website, at least, and validate','juiz_ltw').'</li>';
	echo '<li>'.__('In the next page, find the 4 informations (consumer key, consumer secret, oauth token and oauth token secret).','juiz_ltw').'</li>';
	echo '<li>'.__('Write them in the fields below (they are big strings of characters).','juiz_ltw').'</li>';
	echo '</ol>';
}

// input for consumer key
function juiz_ltw_setting_input_consumer_key() {
	$options = get_option( JUIZ_LTW_SETTING_NAME );
	if ( is_array($options) ) {
		$cons_key = isset($options['consumer_key']) ? $options['consumer_key'] : '';
	echo '<p class="juiz_ltw_options_p">
			<input id="juiz_ltw_consumer_key" value="'.esc_attr($cons_key).'" name="'.JUIZ_LTW_SETTING_NAME.'[consumer_key]" type="text" class="juiz_text_big">
	  	</p>';
	}
}

// input for consumer key
function juiz_ltw_setting_input_consumer_secret() {
	$options = get_option( JUIZ_LTW_SETTING_NAME );
	if ( is_array($options) ) {
		$cons_secret = isset($options['consumer_secret']) ? $options['consumer_secret'] : '';
	echo '<p class="juiz_ltw_options_p">
			<input id="juiz_ltw_consumer_secret" value="'.esc_attr($cons_secret).'" name="'.JUIZ_LTW_SETTING_NAME.'[consumer_secret]" type="text" class="juiz_text_big">
	  	</p>';
	}
}

// input for consumer key
function juiz_ltw_setting_input_oauth_token() {
	$options = get_option( JUIZ_LTW_SETTING_NAME );
	if ( is_array($options) ) {
		$oauth_token = isset($options['oauth_token']) ? $options['oauth_token'] : '';
	echo '<p class="juiz_ltw_options_p">
			<input id="juiz_ltw_oauth_token" value="'.esc_attr($oauth_token).'" name="'.JUIZ_LTW_SETTING_NAME.'[oauth_token]" type="text" class="juiz_text_big">
	  	</p>';
	}
}

// input for consumer key
function juiz_ltw_setting_input_oauth_token_secret() {
	$options = get_option( JUIZ_LTW_SETTING_NAME );
	if ( is_array($options) ) {
		$oauth_token_secret = isset($options['oauth_token_secret']) ? $options['oauth_token_secret'] : '';
	echo '<p class="juiz_ltw_options_p">
			<input id="juiz_ltw_oauth_token_secret" value="'.esc_attr($oauth_token_secret).'" name="'.JUIZ_LTW_SETTING_NAME.'[oauth_token_secret]" type="text" class="juiz_text_big">
	  	</p>';
	}
}


// second section text
function juiz_ltw_section_text_general() {
	echo '<p class="juiz_ltw_section_intro">'. __('Some general settings', 'juiz_ltw') .'</p>';
}
// radio fields rss change
function juiz_ltw_setting_radio_default_style() {

	$options = get_option( JUIZ_LTW_SETTING_NAME );

	if ( is_array($options) ) {
		$n0 = $n1 = "";
		${'n'.$options['default_styles']} = " checked='checked'";
	
		echo '<p class="juiz_ltw_options">
					<input id="jltw_css_y" value="1" name="'.JUIZ_LTW_SETTING_NAME.'[default_styles]" type="radio" '.$n1.' />&nbsp;<label for="jltw_css_y">'. __('Yes', 'juiz_ltw') . '</label>

					<input id="jltw_css_n" value="0" name="'.JUIZ_LTW_SETTING_NAME.'[default_styles]" type="radio" '.$n0.' />&nbsp;<label for="jltw_css_n">'. __('No', 'juiz_ltw') . '</label>
			</p>';
	}
}



// third section text
function juiz_ltw_section_text_fallback() {
	echo '<p class="juiz_ltw_section_intro">'. __('If API 1.1 is out of rate limit', 'juiz_ltw') .'</p>';
}
// radio fields rss change
function juiz_ltw_setting_radio_rss_change() {

	$options = get_option( JUIZ_LTW_SETTING_NAME );
	if ( is_array($options) ) {
		$n0 = $n1 = "";
		${'n'.$options['change_rss_feed']} = " checked='checked'";
	
		echo '<p class="juiz_ltw_options">
					<input id="jltw_change_y" value="1" name="'.JUIZ_LTW_SETTING_NAME.'[change_rss_feed]" type="radio" '.$n1.' />&nbsp;<label for="jltw_change_y">'. __('Yes', 'juiz_ltw') . '</label>

					<input id="jltw_change_n" value="0" name="'.JUIZ_LTW_SETTING_NAME.'[change_rss_feed]" type="radio" '.$n0.' />&nbsp;<label for="jltw_change_n">'. __('No', 'juiz_ltw') . '</label>
			</p>';
	}
}



// The page layout/form

function juiz_ltw_settings_page() {
	?>
	<div id="juiz-ltw" class="wrap">
		<div id="icon-options-general" class="icon32">&nbsp;</div>
		<h2><?php _e('Manage Juiz Last Tweet Widget', 'juiz_ltw') ?></h2>

		<p class="jltw_info">
			<?php echo sprintf(__('You can use %s[jltw]%s or %s[tweets]%s shortcode with some attributes.','juiz_ltw'), '<code>','</code>', '<code>','</code>'); ?>
			<br />
			<?php _e('Example with all available attributes:','juiz_ltw') ?>
			<code>[tweets username="creativejuiz" nb="2" avatar="1" cache="3600" transition="0" delay="0" links="1"]</code>
			<br />
			<?php echo sprintf(__('See %sthe documentation%s for more information', 'juiz_ltw'),'<a href="'.JUIZ_LTW_PLUGIN_URL.'documentation.html" target="_blank">','</a>'); ?>
		</p>
		<form method="post" action="options.php">
			<?php
				settings_fields( JUIZ_LTW_SETTING_NAME );
				do_settings_sections( JUIZ_LTW_SLUG );
				submit_button();
			?>
		</form>
		
		<p class="juiz_bottom_links">
			<em><?php _e('Like it? Support this plugin! Thank you.', 'juiz_ltw') ?></em>
			<a class="juiz_paypal" target="_blank" href="https://www.paypal.com/cgi-bin/webscr?cmd=_donations&amp;business=P39NJPCWVXGDY&amp;lc=FR&amp;item_name=Juiz%20Last%20Tweet%20Widget%20%2d%20WordPress%20Plugin&amp;currency_code=EUR&amp;bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHostedGuest"><?php _e('Donate', 'juiz_ltw') ?></a>
			<a class="juiz_twitter" target="_blank" href="https://twitter.com/intent/tweet?source=webclient&amp;hastags=WordPress,Plugin&amp;text=Juiz%20Last%20Tweet%20Widget%20is%20an%20awesome%20WordPress%20plugin%20to%20display%20tweets!%20Try%20it!&amp;url=http://wordpress.org/extend/plugins/juiz-last-tweet-widget/&amp;related=geoffrey_crofte&amp;via=geoffrey_crofte"><?php _e('Tweet it', 'juiz_ltw') ?></a>
			<a class="juiz_rate" target="_blank" href="http://wordpress.org/support/view/plugin-reviews/juiz-last-tweet-widget"><?php _e('Rate it', 'juiz_ltw') ?></a>
			<a target="_blank" href="<?php echo JUIZ_LTW_PLUGIN_URL; ?>documentation.html"><?php _e('Documentation','juiz_ltw'); ?> (en)</a>
		</p>
	</div>
	<?php
}
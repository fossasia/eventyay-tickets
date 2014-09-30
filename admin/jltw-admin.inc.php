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
	$jltw_options = get_option( JUIZ_LTW_SETTING_NAME );

	if( !$jltw_options ) {
		update_option( JUIZ_LTW_SETTING_NAME, array(
			'consumer_key' 			=> '',
			'consumer_secret' 		=> '',
			'oauth_token'			=> '',
			'oauth_token_secret'	=> '',
			'default_styles'		=> 1,
			'css_style_version'		=> 1,
			'show_nb_of_followers'	=> 0, //for the next updates... chuuuut, keep it secret ;)
			'flat_design_bgcolor'	=> '#',
			'links_colors'			=> array(
				'hastag'	=> '#',
				'username'	=> '#',
				'weblink'	=> '#'
			)
		));
	}
	// version 1.2.2 to 1.3.0
	else {
		if ( is_array($jltw_options['links_colors']) && $jltw_options['links_colors']['hastag']=='') {
			$jltw_options['links_colors'] = array('hastag'=>'#','username'=>'#','weblink'=>'#');
			update_option(JUIZ_LTW_SETTING_NAME , $jltw_options);
		}
		if ( isset($jltw_options['flat_design_bgcolor']) && $jltw_options['flat_design_bgcolor']=='') {
			$jltw_options['flat_design_bgcolor'] = "#";
			update_option(JUIZ_LTW_SETTING_NAME , $jltw_options);
		}
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
	
	add_settings_field('juiz_ltw_twitter_user','<label for="juiz_ltw_consumer_key">'. __('API Key', 'juiz_ltw').'</label>' , 'juiz_ltw_setting_input_consumer_key', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_twitter_api');
	add_settings_field('juiz_ltw_consumer_secret','<label for="juiz_ltw_consumer_secret">'. __('API Secret', 'juiz_ltw').'</label>' , 'juiz_ltw_setting_input_consumer_secret', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_twitter_api');
	add_settings_field('juiz_ltw_oauth_token', '<label for="juiz_ltw_oauth_token">'.__('Access Token', 'juiz_ltw').'</label>' , 'juiz_ltw_setting_input_oauth_token', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_twitter_api');
	add_settings_field('juiz_ltw_oauth_token_secret', '<label for="juiz_ltw_oauth_token_secret">'.__('Access Token Secret', 'juiz_ltw').'</label>' , 'juiz_ltw_setting_input_oauth_token_secret', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_twitter_api');

	add_settings_section('juiz_ltw_plugin_general', __('General settings','juiz_ltw'), 'juiz_ltw_section_text_general', JUIZ_LTW_SLUG);
	add_settings_field('juiz_ltw_rss_change', __('Use default appareance/styles?', 'juiz_ltw'), 'juiz_ltw_setting_radio_default_style', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_general');
	add_settings_field('juiz_ltw_styles', __('Which style do you want?','juiz_ltw'), 'juiz_ltw_setting_style', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_general');

	add_settings_section('juiz_ltw_plugin_custom_styles', __('Customization','juiz_ltw'), 'juiz_ltw_section_text_custom', JUIZ_LTW_SLUG);
	add_settings_field('juiz_ltw_links_colors_hashtag', '<label for="picker-hash">'.__('Color for hashtag links', 'juiz_ltw').'<br /><em>'.__('Hexadecimal value', 'juiz_ltw').'</em></label>', 'juiz_ltw_setting_color_hashlinks', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_custom_styles');
	add_settings_field('juiz_ltw_links_colors_usertag', '<label for="picker-user">'.__('Color for user links', 'juiz_ltw').'<br /><em>'.__('Hexadecimal value', 'juiz_ltw').'</em></label>', 'juiz_ltw_setting_color_userlinks', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_custom_styles');
	add_settings_field('juiz_ltw_links_colors_webtag', '<label for="picker-web">'.__('Color for classical links', 'juiz_ltw').'<br /><em>'.__('Hexadecimal value', 'juiz_ltw').'</em></label>', 'juiz_ltw_setting_color_weblinks', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_custom_styles');
	add_settings_field('juiz_ltw_flat_color', '<label for="picker-flat">'.__('Color for background', 'juiz_ltw').'<br /><em>'.__('Hexadecimal value', 'juiz_ltw').'</em></label>', 'juiz_ltw_setting_flat_design', JUIZ_LTW_SLUG, 'juiz_ltw_plugin_custom_styles');
	

}
add_filter('admin_init','add_juiz_ltw_plugin_options');


// sanitize posted data

function juiz_ltw_sanitize($options) {

	$regexp = '#\#[a-fA-F0-9]{3}#';

	$newoptions['default_styles']		= $options['default_styles']==1 ? 1 : 0;
	$newoptions['consumer_key']			= sanitize_text_field( $options['consumer_key'] );
	$newoptions['consumer_secret']		= sanitize_text_field( $options['consumer_secret'] );
	$newoptions['oauth_token']			= sanitize_text_field( $options['oauth_token'] );
	$newoptions['oauth_token_secret']	= sanitize_text_field( $options['oauth_token_secret'] );

	// new options in 1.3.0
	$newoptions['css_style_version']	= intval( $options['css_style_version'] );
	$newoptions['flat_design_bgcolor'] 	= ( isset($options['flat_design_bgcolor']) && preg_match( $regexp, $options['flat_design_bgcolor'] )) ? $options['flat_design_bgcolor'] : '#';
	$newoptions['links_colors'] 		= is_array( $options['links_colors'] ) ? $options['links_colors'] : array('hastag'=>'#','username'=>'#','weblink'=>'#');
	foreach( $newoptions['links_colors'] as $type => $v ) {
		if ( $v == '' ) $newoptions['links_colors'][$type] = '#';
		else {
			$newoptions['links_colors'][$type] = preg_match( $regexp, $v ) ? $v : '#';
		}
	}

	return $newoptions;
}

// first section text
function juiz_ltw_section_text() {
	echo '<p class="juiz_ltw_section_intro">'. __('You need to create a Twitter plugin to use Juiz Last Tweet Widget because of new API 1.1 rules of Twitter.', 'juiz_ltw') .' <button type="button" class="button juiz_how_to">'.__('How to?','juiz_ltw').'</button></p>';
	echo '<ol class="juiz_ltw_section_intro juiz_next_help">';
	echo '<li>'.sprintf(__('Go to the %sTwitter Developer Center%s to create an app, and create an account if necessary (you can use your Twitter account)','juiz_ltw'),'<a href="https://dev.twitter.com/apps/new" target="_blank">','</a>').'</li>';
	echo '<li>'.__('Give it a name, description and website, at least, and validate','juiz_ltw').'</li>';
	echo '<li>'.__('In the next page, find the 4 informations (API key, API secret, Access token and Access token secret).','juiz_ltw').'</li>';
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
function juiz_ltw_setting_style() {
	$options = get_option( JUIZ_LTW_SETTING_NAME );

	if ( is_array($options) ) {
		$style_version = isset($options['css_style_version'])? intval($options['css_style_version']) : 1;
		$vers_1 = $vers_2 = $vers_3 = '';
		${'vers_'.$style_version} = " checked='checked'";
		echo '<p>
				<input type="radio" name="'.JUIZ_LTW_SETTING_NAME.'[css_style_version]" id="style_default" '.$vers_1.' value="1"><label for="style_default">'.__('Default style','juiz_ltw').'</label>
				<span id="flat-styles">
					<input type="radio" name="'.JUIZ_LTW_SETTING_NAME.'[css_style_version]" id="style_light" '.$vers_2.' value="2"><label for="style_light">'.__('Flat Light style','juiz_ltw').'</label>
					<input type="radio" name="'.JUIZ_LTW_SETTING_NAME.'[css_style_version]" id="style_dark" '.$vers_3.' value="3"><label for="style_dark">'.__('Flat Dark style','juiz_ltw').'</label>
				</span>
				<button type="button" class="button juiz_how_to" title="'.__('Help', 'juiz_ltw').'">?</button>
			</p>
			<p class="juiz_next_help"><em>'.__('Light style is when you have light background color (need dark texts). Dark style&hellip; is the opposite','juiz_ltw').'</em></p>';
	}
}

// third section for customization
function juiz_ltw_section_text_custom() {
	echo '<p class="juiz_ltw_section_intro">'. __('You can now customize some colors!', 'juiz_ltw') .'</p>';
}
function juiz_ltw_setting_color_hashlinks() {
	
	$options = get_option( JUIZ_LTW_SETTING_NAME );

	if ( is_array($options) ) {
		$hash_color = isset($options['links_colors']['hastag']) ? $options['links_colors']['hastag'] : '#';
		echo '<p class="juiz_color_input_parent">
					<input type="text" name="'.JUIZ_LTW_SETTING_NAME.'[links_colors][hastag]" id="picker-hash" value="'.$hash_color.'" /> 
		 	  </p>
		  		<div id="color-hash" class="jltw_color_picker"></div>';
	}
}
function juiz_ltw_setting_color_userlinks() {

	$options = get_option( JUIZ_LTW_SETTING_NAME );

	if ( is_array($options) ) {
		$user_color = isset($options['links_colors']['username']) ? $options['links_colors']['username'] : '#';
		echo '<p class="juiz_color_input_parent">
					<input type="text" name="'.JUIZ_LTW_SETTING_NAME.'[links_colors][username]" id="picker-user" value="'.$user_color.'" /> 
			  </p>
			  <div id="color-user" class="jltw_color_picker"></div>';
	}
}
function juiz_ltw_setting_color_weblinks() {
	
	$options = get_option( JUIZ_LTW_SETTING_NAME );

	if ( is_array($options) ) {
		$web_color = isset($options['links_colors']['weblink']) ? $options['links_colors']['weblink'] : '#';
		echo '<p class="juiz_color_input_parent">
					<input type="text" name="'.JUIZ_LTW_SETTING_NAME.'[links_colors][weblink]" id="picker-web" value="'.$web_color.'" /> 
			  </p>
			  <div id="color-web" class="jltw_color_picker"></div>';
	}
}
// flat options
function juiz_ltw_setting_flat_design() {

	$options = get_option( JUIZ_LTW_SETTING_NAME );

	if ( is_array($options) ) {
		$flat_color = isset($options['flat_design_bgcolor']) ? $options['flat_design_bgcolor'] : '#';
		echo '<div class="juiz_color_input_parent p-like">
				<input type="text" name="'.JUIZ_LTW_SETTING_NAME.'[flat_design_bgcolor]" id="picker-flat" value="'.$flat_color.'" />
				<p class="juiz_advices juiz_use_flat_advice">
					<em>'.sprintf(__('You need to activate one of the %sprevious Flat Style%s','juiz_ltw'), '<a href="#flat-styles">', '</a>').'</em>
				</p>
				<p class="juiz_advices juiz_use_light_advice">
					<em>'.sprintf(__('You should use the %sLight Flat style%s to have better color contrast','juiz_ltw'), '<a href="#style_light">', '</a>').'</em>
				</p>
				<p class="juiz_advices juiz_use_dark_advice">
					<em>'.sprintf(__('You should use the %sDark Flat style%s to have better color contrast','juiz_ltw'), '<a href="#style_dark">', '</a>').'</em>
				</p>
			</div>
			<div id="color-flat" class="jltw_color_picker"></div>';
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
				wp_enqueue_script('jquery_color_picker', JUIZ_LTW_PLUGIN_URL.'admin/js/color-picker/farbtastic.js', array('jquery'), '1.0.0', false);
				wp_enqueue_style('jquery_color_picker', JUIZ_LTW_PLUGIN_URL.'admin/js/color-picker/farbtastic.css', array(), '1.0.0', 'all');

				settings_fields( JUIZ_LTW_SETTING_NAME );
				do_settings_sections( JUIZ_LTW_SLUG );
				submit_button();
			?>
			<script type="text/javascript" charset="utf-8">
				jQuery(document).ready(function($) {
					$('#color-hash').farbtastic('#picker-hash');
					$('#color-user').farbtastic('#picker-user');
					$('#color-web').farbtastic('#picker-web');
					$('#color-flat').farbtastic('#picker-flat');

					$(".jltw_color_picker").hide();
					$('[id^="picker"]').on("focus", function(){
						$(".jltw_color_picker").slideUp(200);
						$(this).closest(".juiz_color_input_parent").next("div[id]").slideDown(200);
					})
				});
			 </script>
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
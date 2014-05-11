;
jQuery(document).ready(function($) {

	/* 
		visibility API 
	*/

	var hidden, visibilityChange;

	// The var hidden is the name of document property
	// The var visibilityChange is the name of the event
	// The var visibilityState is the state property

	if (typeof document.hidden !== "undefined") {
		hidden = "hidden";
		visibilityChange = "visibilitychange";
		visibilityState = "visibilityState";
	} 
	else if (typeof document.mozHidden !== "undefined") {
		hidden = "mozHidden";
		visibilityChange = "mozvisibilitychange";
		visibilityState = "mozVisibilityState";
	} else if (typeof document.msHidden !== "undefined") {
		hidden = "msHidden";
		visibilityChange = "msvisibilitychange";
		visibilityState = "msVisibilityState";
	} else if (typeof document.webkitHidden !== "undefined") {
		hidden = "webkitHidden";
		visibilityChange = "webkitvisibilitychange";
		visibilityState = "webkitVisibilityState";
	}

	if( $('.juiz_ltw_autoslide').length > 0 ) {
	
		$('.juiz_ltw_autoslide').each(function(){
		
			// some vars
			var $parent = $(this);
			var $tweets = $parent.find('li');
			var $first_tweet = $tweets.filter(':first');
			var ltw_the_delay = $parent.data('delay');
			var the_speed = 300;
			var ltw_interval;


			// some functions

			function createAutoSlide() {
				if(!ltw_interval)
					ltw_interval = setInterval(juiz_ltw_next_one, ltw_the_delay*1000);
			}
			function removeAutoSlide() {
				clearInterval(ltw_interval);
				ltw_interval = false;
			}
			// visibility API
			document.addEventListener(visibilityChange, checkVisibility, false);
			function checkVisibility() {
				//document[hidden] // true or false
				//document[visibilityState] // visible or hidden
				if ( document[hidden] === true ) {
					removeAutoSlide();
				}
				if ( document[hidden] === false ) {
					createAutoSlide();
				}
			}

			
			$('.juiz_last_tweet_tweetlist').css('width', $('.juiz_last_tweet_tweetlist').width())

			if ( $tweets.length > 1 ) {
				$tweets.filter(':not(":first")').hide();
				$first_tweet.addClass('jltw_current');
				
				$parent.addClass('hasjs');
				
				$parent.prepend($parent.find('.user_avatar'));
				$parent.find('ul .user_avatar').remove();
				
				function juiz_ltw_next_one() {

					$current_one = $($parent).find('.jltw_current');
					$the_next = $current_one.next('li');

					if( $the_next.length > 0 ) {
						$current_one.hide().removeClass('jltw_current');
						$the_next.fadeTo(50, .05); // bug fix to have the real height before animation
						$parent.find('.juiz_last_tweet_tweetlist').animate({'height': $current_one.next('li').height() }, the_speed, function(){
							$the_next.fadeTo(the_speed, 1).addClass('jltw_current');
						});
					}
					else {
						$current_one.hide().removeClass('jltw_current');
						$first_tweet.fadeTo(50, .05); // bug fix to have the real height before animation
						$parent.find('.juiz_last_tweet_tweetlist').animate({'height': $first_tweet.height() }, the_speed, function(){
							$first_tweet.addClass('jltw_current').fadeTo(the_speed, 1);
						});
					}
						
				}
				
				createAutoSlide();
				
				$tweets.mouseenter(function(){
					removeAutoSlide();
				})
				.mouseleave(function(){
					createAutoSlide();
				});
			}
			
		});
		
	}

});
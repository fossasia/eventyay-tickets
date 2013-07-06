;
jQuery(document).ready(function($){

	if( $('.juiz_ltw_autoslide').length > 0 ) {
	
		$('.juiz_ltw_autoslide').each(function(){
		
			var $parent = $(this);
			var $tweets = $parent.find('li');
			var $first_tweet = $tweets.filter(':first');
			var ltw_the_delay = $parent.data('delay');
			var the_speed = 300;
			var ltw_interval;
			
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
				
				ltw_interval = setInterval(juiz_ltw_next_one, ltw_the_delay*1000);
				
				$tweets.mouseenter(function(){
					clearInterval(ltw_interval);
					ltw_interval = false;
				})
				.mouseleave(function(){
					if(!ltw_interval)
						ltw_interval = setInterval(juiz_ltw_next_one, ltw_the_delay*1000);
				});
			}
			
		});
		
	}

});